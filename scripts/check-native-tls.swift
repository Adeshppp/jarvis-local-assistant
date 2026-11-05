import Foundation
import Security
let path=CommandLine.arguments[1]
let data=try Data(contentsOf: URL(fileURLWithPath:path))
let cert=SecCertificateCreateWithData(nil,data as CFData)!
let root=SecCertificateCreateWithData(nil,try Data(contentsOf:URL(fileURLWithPath:CommandLine.arguments[2])) as CFData)!
var trust: SecTrust?
SecTrustCreateWithCertificates(cert,SecPolicyCreateSSL(true,"localhost" as CFString),&trust)
SecTrustSetAnchorCertificates(trust!,[root] as CFArray)
SecTrustSetAnchorCertificatesOnly(trust!,true)
SecTrustSetNetworkFetchAllowed(trust!,false)
var failure: CFError?
let valid=SecTrustEvaluateWithError(trust!,&failure)
print("Native TLS trust:",valid)
if let failure=failure {print(failure)}
if let details=SecTrustCopyResult(trust!) {print(details)}
