import Foundation

// MARK: - JSON Response Helpers

struct JSONResponse {
    let success: Bool
    let data: [String: Any]?
    let error: String?

    func print() {
        var dict: [String: Any] = ["success": success]
        if let data = data {
            dict["data"] = data
        }
        if let error = error {
            dict["error"] = error
        }

        if let jsonData = try? JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted, .sortedKeys]),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            Swift.print(jsonString)
        }
    }
}

func successResponse(_ data: [String: Any]) {
    JSONResponse(success: true, data: data, error: nil).print()
}

func errorResponse(_ message: String) -> Never {
    JSONResponse(success: false, data: nil, error: message).print()
    exit(1)
}

// MARK: - AppleScript Helpers

func runAppleScript(_ script: String) -> (output: String?, error: String?) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-e", script]

    let outputPipe = Pipe()
    let errorPipe = Pipe()
    process.standardOutput = outputPipe
    process.standardError = errorPipe

    do {
        try process.run()
        process.waitUntilExit()

        let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
        let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()

        let output = String(data: outputData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
        let error = String(data: errorData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)

        if process.terminationStatus == 0 {
            return (output, nil)
        } else {
            return (nil, error ?? "AppleScript execution failed")
        }
    } catch {
        return (nil, error.localizedDescription)
    }
}

// MARK: - Note Parsing

func parseNotesList(_ output: String) -> [[String: Any]] {
    // Output format: id|title|folder|creationDate|modificationDate
    var notes: [[String: Any]] = []

    for line in output.components(separatedBy: "\n") {
        let parts = line.components(separatedBy: "|")
        if parts.count >= 5 {
            notes.append([
                "id": parts[0],
                "title": parts[1],
                "folder": parts[2],
                "createdAt": parts[3],
                "modifiedAt": parts[4]
            ])
        }
    }

    return notes
}

func parseFoldersList(_ output: String) -> [[String: Any]] {
    var folders: [[String: Any]] = []

    for line in output.components(separatedBy: "\n") {
        let parts = line.components(separatedBy: "|")
        if parts.count >= 2 {
            folders.append([
                "id": parts[0],
                "name": parts[1]
            ])
        }
    }

    return folders
}

// MARK: - Commands

func listFolders() {
    let script = """
    tell application "Notes"
        set output to ""
        repeat with f in folders
            set output to output & (id of f) & "|" & (name of f) & linefeed
        end repeat
        return output
    end tell
    """

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to list folders: \(error)")
    }

    let folders = parseFoldersList(output ?? "")
    successResponse([
        "folders": folders,
        "count": folders.count
    ])
}

func listNotes(folderName: String?) {
    var script: String

    if let folder = folderName {
        script = """
        tell application "Notes"
            set output to ""
            set theFolder to missing value
            repeat with a in accounts
                repeat with f in folders of a
                    if name of f is "\(folder)" then
                        set theFolder to f
                        exit repeat
                    end if
                end repeat
                if theFolder is not missing value then exit repeat
            end repeat
            if theFolder is missing value then
                error "Folder not found: \(folder)"
            end if
            repeat with n in notes of theFolder
                set noteId to id of n
                set noteTitle to name of n
                set createdDate to creation date of n as string
                set modifiedDate to modification date of n as string
                set output to output & noteId & "|" & noteTitle & "|" & "\(folder)" & "|" & createdDate & "|" & modifiedDate & linefeed
            end repeat
            return output
        end tell
        """
    } else {
        // Iterate through folders to get notes - accessing notes directly from global collection
        // causes -1728 error when trying to get container property
        script = """
        tell application "Notes"
            set output to ""
            repeat with f in folders
                set folderName to name of f
                repeat with n in notes of f
                    set noteId to id of n
                    set noteTitle to name of n
                    set createdDate to creation date of n as string
                    set modifiedDate to modification date of n as string
                    set output to output & noteId & "|" & noteTitle & "|" & folderName & "|" & createdDate & "|" & modifiedDate & linefeed
                end repeat
            end repeat
            return output
        end tell
        """
    }

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to list notes: \(error)")
    }

    let notes = parseNotesList(output ?? "")
    successResponse([
        "notes": notes,
        "count": notes.count
    ])
}

func getNote(noteId: String) {
    // AppleScript note IDs look like: x-coredata://...
    // We need to escape special characters
    let escapedId = noteId.replacingOccurrences(of: "\"", with: "\\\"")

    // Find the note and its folder by searching through all folders
    // Direct container access on notes can cause -1728 error
    let script = """
    tell application "Notes"
        set foundNote to missing value
        set foundFolder to ""
        repeat with f in folders
            repeat with n in notes of f
                if id of n is "\(escapedId)" then
                    set foundNote to n
                    set foundFolder to name of f
                    exit repeat
                end if
            end repeat
            if foundNote is not missing value then exit repeat
        end repeat
        if foundNote is missing value then
            error "Note not found"
        end if
        set noteId to id of foundNote
        set noteTitle to name of foundNote
        set noteBody to plaintext of foundNote
        set createdDate to creation date of foundNote as string
        set modifiedDate to modification date of foundNote as string
        return noteId & "|" & noteTitle & "|" & foundFolder & "|" & createdDate & "|" & modifiedDate & "|BODY_START|" & noteBody
    end tell
    """

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to get note: \(error)")
    }

    guard let output = output else {
        errorResponse("Empty response from Notes")
    }

    // Parse the output
    let bodyMarker = "|BODY_START|"
    guard let bodyStart = output.range(of: bodyMarker) else {
        errorResponse("Failed to parse note output")
    }

    let metadata = String(output[..<bodyStart.lowerBound])
    let body = String(output[bodyStart.upperBound...])

    let parts = metadata.components(separatedBy: "|")
    guard parts.count >= 5 else {
        errorResponse("Failed to parse note metadata")
    }

    let note: [String: Any] = [
        "id": parts[0],
        "title": parts[1],
        "folder": parts[2],
        "createdAt": parts[3],
        "modifiedAt": parts[4],
        "body": body
    ]

    successResponse(["note": note])
}

func createNote() {
    // Read JSON from stdin
    let inputData = FileHandle.standardInput.readDataToEndOfFile()
    guard !inputData.isEmpty,
          let json = try? JSONSerialization.jsonObject(with: inputData) as? [String: Any] else {
        errorResponse("Invalid JSON input. Expected: {\"title\": \"...\", \"body\": \"...\", \"folder\": \"...\"}")
    }

    guard let title = json["title"] as? String else {
        errorResponse("Missing required field: title")
    }

    let body = json["body"] as? String ?? ""
    let folder = json["folder"] as? String ?? "Notes"

    // Escape for AppleScript
    let escapedTitle = title.replacingOccurrences(of: "\"", with: "\\\"")
    let escapedBody = body.replacingOccurrences(of: "\"", with: "\\\"")
    let escapedFolder = folder.replacingOccurrences(of: "\"", with: "\\\"")

    // Use the folder name we already have instead of querying container
    let script = """
    tell application "Notes"
        set actualFolderName to "\(escapedFolder)"
        try
            set theFolder to folder "\(escapedFolder)"
        on error
            set theFolder to default folder
            set actualFolderName to name of default folder
        end try
        set newNote to make new note at theFolder with properties {name:"\(escapedTitle)", body:"\(escapedBody)"}
        set noteId to id of newNote
        set noteTitle to name of newNote
        return noteId & "|" & noteTitle & "|" & actualFolderName
    end tell
    """

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to create note: \(error)")
    }

    guard let output = output else {
        errorResponse("Empty response from Notes")
    }

    let parts = output.components(separatedBy: "|")
    guard parts.count >= 3 else {
        errorResponse("Failed to parse note creation response")
    }

    successResponse([
        "created": true,
        "note": [
            "id": parts[0],
            "title": parts[1],
            "folder": parts[2]
        ]
    ])
}

func updateNote(noteId: String) {
    // Read JSON from stdin
    let inputData = FileHandle.standardInput.readDataToEndOfFile()
    guard !inputData.isEmpty,
          let json = try? JSONSerialization.jsonObject(with: inputData) as? [String: Any] else {
        errorResponse("Invalid JSON input")
    }

    let escapedId = noteId.replacingOccurrences(of: "\"", with: "\\\"")

    var updates: [String] = []

    if let title = json["title"] as? String {
        let escapedTitle = title.replacingOccurrences(of: "\"", with: "\\\"")
        updates.append("set name of theNote to \"\(escapedTitle)\"")
    }

    if let body = json["body"] as? String {
        let escapedBody = body.replacingOccurrences(of: "\"", with: "\\\"")
        updates.append("set body of theNote to \"\(escapedBody)\"")
    }

    if updates.isEmpty {
        errorResponse("No fields to update")
    }

    let updateCommands = updates.joined(separator: "\n            ")

    // Find the note by searching through folders to avoid container access issue
    let script = """
    tell application "Notes"
        set foundNote to missing value
        set foundFolder to ""
        repeat with f in folders
            repeat with n in notes of f
                if id of n is "\(escapedId)" then
                    set foundNote to n
                    set foundFolder to name of f
                    exit repeat
                end if
            end repeat
            if foundNote is not missing value then exit repeat
        end repeat
        if foundNote is missing value then
            error "Note not found"
        end if
        set theNote to foundNote
        \(updateCommands)
        set noteId to id of theNote
        set noteTitle to name of theNote
        return noteId & "|" & noteTitle & "|" & foundFolder
    end tell
    """

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to update note: \(error)")
    }

    guard let output = output else {
        errorResponse("Empty response from Notes")
    }

    let parts = output.components(separatedBy: "|")
    guard parts.count >= 3 else {
        errorResponse("Failed to parse note update response")
    }

    successResponse([
        "updated": true,
        "note": [
            "id": parts[0],
            "title": parts[1],
            "folder": parts[2]
        ]
    ])
}

func deleteNote(noteId: String) {
    let escapedId = noteId.replacingOccurrences(of: "\"", with: "\\\"")

    let script = """
    tell application "Notes"
        try
            set theNote to note id "\(escapedId)"
            set noteTitle to name of theNote
            delete theNote
            return noteTitle
        on error
            error "Note not found"
        end try
    end tell
    """

    let (output, error) = runAppleScript(script)

    if let error = error {
        errorResponse("Failed to delete note: \(error)")
    }

    successResponse([
        "deleted": true,
        "noteId": noteId,
        "title": output ?? ""
    ])
}

func printHelp() {
    let help = """
    hestia-notes-cli - Notes integration for Hestia

    USAGE:
        hestia-notes-cli <command> [arguments]

    COMMANDS:
        list-folders                List all note folders
        list-notes                  List notes (with optional folder filter)
            --folder <name>         Filter by folder name
        get-note <note-id>          Get details and content of a note
        create-note                 Create a new note (reads JSON from stdin)
        update-note <note-id>       Update a note (reads JSON from stdin)
        delete-note <note-id>       Delete a note
        help, --help, -h            Show this help message

    CREATE/UPDATE JSON FORMAT:
        {
            "title": "Meeting Notes",
            "body": "Discussion points...",
            "folder": "Work"
        }

    NOTE:
        - Note IDs are in the format: x-coredata://...
        - This tool uses AppleScript to interact with Notes.app
        - First run may require accessibility permissions

    OUTPUT:
        All commands output JSON with format:
        {"success": true/false, "data": {...}, "error": "..."}
    """
    print(help)
}

// MARK: - Argument Parsing

func parseArguments() -> (command: String, args: [String: String], positional: [String]) {
    let arguments = CommandLine.arguments
    guard arguments.count > 1 else {
        return ("help", [:], [])
    }

    let command = arguments[1]
    var named: [String: String] = [:]
    var positional: [String] = []

    var i = 2
    while i < arguments.count {
        let arg = arguments[i]
        if arg.hasPrefix("--") {
            let key = String(arg.dropFirst(2))
            if i + 1 < arguments.count && !arguments[i + 1].hasPrefix("--") {
                named[key] = arguments[i + 1]
                i += 2
            } else {
                named[key] = "true"
                i += 1
            }
        } else {
            positional.append(arg)
            i += 1
        }
    }

    return (command, named, positional)
}

// MARK: - Main

let (command, args, positional) = parseArguments()

switch command {
case "list-folders":
    listFolders()

case "list-notes":
    listNotes(folderName: args["folder"])

case "get-note":
    guard let noteId = positional.first else {
        errorResponse("Usage: get-note <note-id>")
    }
    getNote(noteId: noteId)

case "create-note":
    createNote()

case "update-note":
    guard let noteId = positional.first else {
        errorResponse("Usage: update-note <note-id>")
    }
    updateNote(noteId: noteId)

case "delete-note":
    guard let noteId = positional.first else {
        errorResponse("Usage: delete-note <note-id>")
    }
    deleteNote(noteId: noteId)

case "help", "--help", "-h":
    printHelp()

default:
    errorResponse("Unknown command: \(command). Use --help for usage.")
}
