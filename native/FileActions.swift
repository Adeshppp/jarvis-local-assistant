import Foundation

do {
    let data=FileHandle.standardInput.readDataToEndOfFile()
    guard let request=try JSONSerialization.jsonObject(with:data) as? [String:String],
          let action=request["action"], let path=request["path"], path.hasPrefix("/") else {
        throw NSError(domain:"Jarvis",code:1,userInfo:[NSLocalizedDescriptionKey:"Invalid file operation"])
    }
    let file=URL(fileURLWithPath:path)
    let manager=FileManager.default
    var result:[String:Any]=[:]
    if action=="trash" {
        var trashed:NSURL?
        try manager.trashItem(at:file,resultingItemURL:&trashed)
        result=["trashed":path,"trash_location":trashed?.path ?? ""]
    } else if action=="move", let destination=request["destination"], destination.hasPrefix("/") {
        try manager.moveItem(at:file,to:URL(fileURLWithPath:destination))
        result=["success":true]
    } else if action=="replace", let replacement=request["replacement"], replacement.hasPrefix("/") {
        _=try manager.replaceItemAt(file,withItemAt:URL(fileURLWithPath:replacement),backupItemName:nil,options:[])
        result=["success":true]
    } else { throw NSError(domain:"Jarvis",code:2,userInfo:[NSLocalizedDescriptionKey:"Unknown file operation"])}
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:result))
} catch {
    FileHandle.standardError.write(Data(error.localizedDescription.utf8));exit(1)
}
