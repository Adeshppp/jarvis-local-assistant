import AppKit
import AVFoundation
import Security
import WebKit

final class App: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, AVSpeechSynthesizerDelegate {
    var status: NSStatusItem!
    var window: NSWindow!
    var web: WKWebView!
    var base: URL!
    var pinned: Data!
    var anchor: Data!
    var serverURL = URL(string: "https://localhost:8765")!
    var isRemote = false
    var documentReady = false
    var pendingToken: String?
    var keychainAccount: String { isRemote ? "remote-client" : "macbook-air" }
    let speech = AVSpeechSynthesizer()
    let service = "local.personal-ai.device"

    func diagnostic(_ event: String, _ detail: String = "") {
        guard let base = base else { return }
        let value = ["event": event, "detail": detail, "time": ISO8601DateFormatter().string(from: Date())]
        if let data = try? JSONSerialization.data(withJSONObject: value, options: .prettyPrinted) {
            try? data.write(to: base.appendingPathComponent("state/desktop-diagnostic.json"), options: .atomic)
        }
        if let data = try? JSONSerialization.data(withJSONObject: value) {
            let url = base.appendingPathComponent("state/desktop-diagnostic.jsonl")
            if !FileManager.default.fileExists(atPath: url.path) { FileManager.default.createFile(atPath: url.path, contents: nil, attributes: [.posixPermissions: 0o600]) }
            if let handle = try? FileHandle(forWritingTo: url) { try? handle.seekToEnd(); try? handle.write(contentsOf: data + Data([10])); try? handle.close() }
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        if let remoteFile = Bundle.main.url(forResource: "remote-client", withExtension: "json"),
           let data = try? Data(contentsOf: remoteFile), let remote = try? JSONSerialization.jsonObject(with: data) as? [String: String],
           let address = remote["server"], let url = URL(string: address), url.scheme == "https", url.port == 8765 {
            isRemote = true; serverURL = url
            base = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/JarvisClient")
            try? FileManager.default.createDirectory(at: base.appendingPathComponent("state/logs"), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            pinned = Bundle.main.url(forResource: "server", withExtension: "der").flatMap { try? Data(contentsOf: $0) }
            anchor = Bundle.main.url(forResource: "ca", withExtension: "der").flatMap { try? Data(contentsOf: $0) }
        } else {
        guard let rootFile = Bundle.main.url(forResource: "project-root", withExtension: "txt"),
              let path = try? String(contentsOf: rootFile, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines) else { return }
        base = URL(fileURLWithPath: path)
        pinned = try? Data(contentsOf: base.appendingPathComponent("state/tls/server.der"))
        anchor = try? Data(contentsOf: base.appendingPathComponent("state/tls/ca.der"))
        }
        speech.delegate = self
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        status.button?.title = "◉ Jarvis"
        let menu = NSMenu()
        for (title, action) in [("Open Jarvis", #selector(show)), ("Start assistant", #selector(startServer)), ("Stop assistant", #selector(stopServer)), ("Mute microphone", #selector(mute)), ("File access permissions…", #selector(fileAccess)), ("Open project folder", #selector(openProject)), ("View logs", #selector(openLogs)), ("Uninstall login services…", #selector(uninstall)), ("Quit desktop client", #selector(quit))] {
            if isRemote && (action == #selector(startServer) || action == #selector(stopServer) || action == #selector(uninstall) || action == #selector(fileAccess)) { continue }
            let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
            item.target = self; menu.addItem(item)
        }
        status.menu = menu
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "native")
        config.preferences.javaScriptCanOpenWindowsAutomatically = false
        let token = ""
        let voices = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("en") }.map { ["name": $0.name, "identifier": $0.identifier] }
        let tokenJSON = String(data: try! JSONSerialization.data(withJSONObject: token, options: .fragmentsAllowed), encoding: .utf8)!
        let voiceJSON = String(data: try! JSONSerialization.data(withJSONObject: voices), encoding: .utf8)!
        config.userContentController.addUserScript(WKUserScript(source: "window.__deviceToken = \(tokenJSON); window.__voices = \(voiceJSON);", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        web = WKWebView(frame: NSRect(x: 0, y: 0, width: 920, height: 790), configuration: config)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self; web.uiDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 920, height: 790), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Jarvis · Local Personal Assistant"
        window.contentView = web
        window.isReleasedWhenClosed = false
        window.center()
        web.load(URLRequest(url: serverURL))
        diagnostic("started", "Loading the authenticated local interface")
        show()
        // Keychain may require an OS approval. Never block window creation while
        // that approval is pending; show the connection screen first.
        DispatchQueue.global(qos: .userInitiated).async {
            let value = self.loadToken()
            DispatchQueue.main.async {
                self.pendingToken = value
                self.injectPendingToken()
            }
        }
    }

    func injectPendingToken() {
        guard documentReady, let token = pendingToken, !token.isEmpty else { return }
        let encoded = String(data: try! JSONSerialization.data(withJSONObject: token, options: .fragmentsAllowed), encoding: .utf8)!
        web.evaluateJavaScript("window.provideNativeToken && window.provideNativeToken(\(encoded))", completionHandler: nil)
        diagnostic("device-token-ready", "Private token supplied to pinned local interface")
    }

    func loadToken() -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: keychainAccount,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        if SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
           let data = result as? Data, let value = String(data: data, encoding: .utf8) { return value }
        let file = base.appendingPathComponent("state/bootstrap-token")
        guard let data = try? Data(contentsOf: file), let value = String(data: data, encoding: .utf8) else { return "" }
        let item: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: keychainAccount,
            kSecValueData as String: data, kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        if SecItemAdd(item as CFDictionary, nil) == errSecSuccess { try? FileManager.default.removeItem(at: file) }
        return value
    }

    @objc func show() { window?.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    func launchctl(_ args: [String]) {
        let process = Process(); process.executableURL = URL(fileURLWithPath: "/bin/launchctl"); process.arguments = args
        do { try process.run() } catch { alert(error.localizedDescription) }
    }
    @objc func startServer() {
        launchctl(["bootstrap", "gui/\(getuid())", base.appendingPathComponent("state/local.personal-ai.server.plist").path])
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { self.web.reload() }
    }
    @objc func stopServer() { mute(); launchctl(["bootout", "gui/\(getuid())/local.personal-ai.server"]) }
    @objc func mute() { web?.evaluateJavaScript("window.closeMicrophone && window.closeMicrophone()", completionHandler: nil); speech.stopSpeaking(at: .immediate) }
    @objc func openProject() { NSWorkspace.shared.open(base) }
    @objc func openLogs() { NSWorkspace.shared.open(base.appendingPathComponent("state/logs")) }
    @objc func fileAccess() {
        let path=(try? String(contentsOf:base.appendingPathComponent("state/backend-app.txt"),encoding:.utf8).trimmingCharacters(in:.whitespacesAndNewlines)) ?? "the backend Python app"
        let notice=NSAlert();notice.messageText="Allow Jarvis to read protected folders"
        notice.informativeText="Jarvis's server runs in Python. In Full Disk Access, add and enable this Python app:\n\n\(path)\n\nThis lets the backend access files you request, including protected Mac folders. macOS requires you to approve this permission. Restart the assistant afterward."
        notice.addButton(withTitle:"Open Privacy Settings");notice.addButton(withTitle:"Reveal Python app");notice.addButton(withTitle:"Cancel")
        let choice=notice.runModal()
        if choice == .alertFirstButtonReturn { NSWorkspace.shared.open(URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles")!) }
        if choice == .alertSecondButtonReturn { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath:path)]) }
    }
    @objc func quit() { mute(); NSApp.terminate(nil) }
    @objc func uninstall() {
        let confirm = NSAlert(); confirm.messageText = "Remove Jarvis login services?"
        confirm.informativeText = "This stops the server and removes its login startup configuration. Your conversations, models and source remain in place."
        confirm.addButton(withTitle: "Remove services"); confirm.addButton(withTitle: "Cancel")
        if confirm.runModal() == .alertFirstButtonReturn {
            mute(); let process = Process(); process.executableURL = base.appendingPathComponent("jarvis"); process.arguments = ["uninstall"]
            do { try process.run() } catch { alert(error.localizedDescription) }
        }
    }
    func alert(_ message: String) { let a = NSAlert(); a.messageText = "Jarvis"; a.informativeText = message; a.runModal() }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == serverURL.host,
              message.frameInfo.securityOrigin.port == serverURL.port,
              let value = message.body as? [String: Any], let action = value["action"] as? String else { return }
        if action == "status", let text = value["text"] as? String { status.button?.toolTip = text }
        if action == "cancelSpeech" { speech.stopSpeaking(at: .immediate) }
        if action == "saveToken", isRemote, let token = value["token"] as? String, token.count < 200 {
            let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: keychainAccount]
            let update: [String: Any] = [kSecValueData as String: Data(token.utf8)]
            if SecItemUpdate(query as CFDictionary, update as CFDictionary) == errSecItemNotFound {
                var item = query; item[kSecValueData as String] = Data(token.utf8)
                item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
                SecItemAdd(item as CFDictionary, nil)
            }
        }
        if action == "speak", let text = value["text"] as? String, text.count <= 32000 {
            speech.stopSpeaking(at: .immediate)
            let utterance = AVSpeechUtterance(string: text)
            let name = value["voice"] as? String ?? "Samantha"
            utterance.voice = AVSpeechSynthesisVoice.speechVoices().first { $0.name == name } ?? AVSpeechSynthesisVoice(language: "en-US")
            let rate = value["rate"] as? Double ?? 185
            utterance.rate = Float(max(0.2, min(0.65, rate / 400)))
            speech.speak(utterance)
        }
        if action == "exportData", let text = value["text"] as? String {
            let directory = base.appendingPathComponent("exports", isDirectory: true)
            do {
                let manager = FileManager.default
                if !manager.fileExists(atPath: directory.path) { try manager.createDirectory(at: directory, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700]) }
                let attrs = try manager.attributesOfItem(atPath: directory.path)
                guard attrs[.type] as? FileAttributeType == .typeDirectory else { return }
                let kind = value["kind"] as? String == "settings" ? "settings" : "memory"
                let url = directory.appendingPathComponent("jarvis-\(kind)-\(UUID().uuidString).json")
                try text.write(to: url, atomically: true, encoding: .utf8)
                try manager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
                NSWorkspace.shared.activateFileViewerSelecting([url])
            } catch { alert(error.localizedDescription) }
        }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        web?.evaluateJavaScript("window.nativeSpokenDone && window.nativeSpokenDone()", completionHandler: nil)
    }

    func webView(_ webView: WKWebView, didReceive challenge: URLAuthenticationChallenge, completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust else {
            completionHandler(.performDefaultHandling, nil); return
        }
        guard let trust = challenge.protectionSpace.serverTrust, let expected = pinned, let ca = anchor,
              let cert = SecCertificateCreateWithData(nil, ca as CFData) else {
            diagnostic("trust-rejected", challenge.protectionSpace.authenticationMethod)
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        SecTrustSetAnchorCertificates(trust, [cert] as CFArray)
        SecTrustSetAnchorCertificatesOnly(trust, true)
        SecTrustSetPolicies(trust, SecPolicyCreateSSL(true, challenge.protectionSpace.host as CFString))
        SecTrustSetNetworkFetchAllowed(trust, false)
        var trustError: CFError?
        if SecTrustEvaluateWithError(trust, &trustError),
           let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate], let leaf = chain.first,
           SecCertificateCopyData(leaf) as Data == expected { diagnostic("trust-accepted"); completionHandler(.useCredential, URLCredential(trust: trust)) }
        else { diagnostic("trust-evaluation-failed", trustError.map { String(describing: $0) } ?? "Certificate pin mismatch"); completionHandler(.cancelAuthenticationChallenge, nil) }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        window.contentView = web
        documentReady = true
        diagnostic("interface-loaded", "Local page navigation completed")
        injectPendingToken()
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        documentReady = false
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        diagnostic("navigation-failed", error.localizedDescription)
        showLoadError(error.localizedDescription)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        diagnostic("navigation-failed", error.localizedDescription)
        showLoadError(error.localizedDescription)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        diagnostic("web-content-restarted")
        webView.reload()
    }

    func showLoadError(_ detail: String) {
        let view = NSView(frame: NSRect(x: 0, y: 0, width: 920, height: 790))
        let label = NSTextField(wrappingLabelWithString: "Jarvis could not load its local interface.\n\n\(detail)\n\nUse the menu-bar Start assistant control, then reopen Jarvis.")
        label.frame = NSRect(x: 50, y: 250, width: 780, height: 200)
        label.font = .systemFont(ofSize: 18)
        view.addSubview(label)
        let retry = NSButton(title: "Retry connection", target: self, action: #selector(retryConnection))
        retry.frame = NSRect(x: 50, y: 220, width: 180, height: 36)
        view.addSubview(retry)
        window.contentView = view
    }

    @objc func retryConnection() { window.contentView = web; web.load(URLRequest(url: serverURL)) }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        diagnostic("navigation-policy", navigationAction.request.url?.absoluteString ?? "missing URL")
        guard let url = navigationAction.request.url, url.scheme == "https", url.host == serverURL.host, url.port == serverURL.port else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        guard origin.host == serverURL.host, origin.port == serverURL.port, type == .microphone else { decisionHandler(.deny); return }
        AVCaptureDevice.requestAccess(for: .audio) { allowed in
            DispatchQueue.main.async { decisionHandler(allowed ? .grant : .deny) }
        }
    }
    func applicationWillTerminate(_ notification: Notification) { mute() }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.run()
