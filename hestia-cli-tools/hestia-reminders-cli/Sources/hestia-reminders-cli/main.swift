import Foundation
import EventKit

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

// MARK: - Date Helpers

let isoFormatter: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter
}()

let dateOnlyFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd"
    return formatter
}()

func parseDate(_ string: String) -> Date? {
    if let date = isoFormatter.date(from: string) {
        return date
    }
    if let date = dateOnlyFormatter.date(from: string) {
        return date
    }
    if string.lowercased() == "today" {
        return Calendar.current.startOfDay(for: Date())
    }
    if string.lowercased() == "tomorrow" {
        return Calendar.current.date(byAdding: .day, value: 1, to: Calendar.current.startOfDay(for: Date()))
    }
    return nil
}

func formatDate(_ date: Date?) -> String? {
    guard let date = date else { return nil }
    return isoFormatter.string(from: date)
}

// MARK: - EventKit Helpers

let eventStore = EKEventStore()

func requestRemindersAccess() -> Bool {
    var granted = false
    let semaphore = DispatchSemaphore(value: 0)

    if #available(macOS 14.0, *) {
        eventStore.requestFullAccessToReminders { success, error in
            granted = success
            semaphore.signal()
        }
    } else {
        eventStore.requestAccess(to: .reminder) { success, error in
            granted = success
            semaphore.signal()
        }
    }

    semaphore.wait()
    return granted
}

func reminderListToDict(_ calendar: EKCalendar) -> [String: Any] {
    return [
        "id": calendar.calendarIdentifier,
        "title": calendar.title,
        "source": calendar.source?.title ?? "Unknown",
        "color": calendar.cgColor?.components?.map { $0 } ?? [],
        "allowsModifications": calendar.allowsContentModifications
    ]
}

func reminderToDict(_ reminder: EKReminder) -> [String: Any] {
    var dict: [String: Any] = [
        "id": reminder.calendarItemIdentifier,
        "title": reminder.title ?? "",
        "list": reminder.calendar?.title ?? "",
        "listId": reminder.calendar?.calendarIdentifier ?? "",
        "isCompleted": reminder.isCompleted,
        "priority": reminder.priority
    ]

    if let dueDate = reminder.dueDateComponents?.date {
        dict["due"] = formatDate(dueDate)
    }
    if let completionDate = reminder.completionDate {
        dict["completedAt"] = formatDate(completionDate)
    }
    if let notes = reminder.notes, !notes.isEmpty {
        dict["notes"] = notes
    }
    if let url = reminder.url {
        dict["url"] = url.absoluteString
    }

    return dict
}

// MARK: - Commands

func listLists() {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied. Please grant access in System Preferences > Privacy & Security > Reminders.")
    }

    let calendars = eventStore.calendars(for: .reminder)
    let listDicts = calendars.map { reminderListToDict($0) }

    successResponse([
        "lists": listDicts,
        "count": calendars.count
    ])
}

func listReminders(listName: String?, showCompleted: Bool, showIncomplete: Bool) {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied. Please grant access in System Preferences > Privacy & Security > Reminders.")
    }

    // Get calendars to search
    var calendars: [EKCalendar]
    if let name = listName {
        calendars = eventStore.calendars(for: .reminder).filter { $0.title.lowercased() == name.lowercased() }
        if calendars.isEmpty {
            errorResponse("Reminder list '\(name)' not found")
        }
    } else {
        calendars = eventStore.calendars(for: .reminder)
    }

    // Create predicate and fetch reminders
    let predicate = eventStore.predicateForReminders(in: calendars)

    var reminders: [EKReminder] = []
    let semaphore = DispatchSemaphore(value: 0)

    eventStore.fetchReminders(matching: predicate) { fetchedReminders in
        reminders = fetchedReminders ?? []
        semaphore.signal()
    }

    semaphore.wait()

    // Filter by completion status
    if showCompleted && !showIncomplete {
        reminders = reminders.filter { $0.isCompleted }
    } else if showIncomplete && !showCompleted {
        reminders = reminders.filter { !$0.isCompleted }
    }
    // If both or neither are specified, show all

    let reminderDicts = reminders.map { reminderToDict($0) }

    successResponse([
        "reminders": reminderDicts,
        "count": reminders.count
    ])
}

func getReminder(reminderId: String) {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied.")
    }

    guard let reminder = eventStore.calendarItem(withIdentifier: reminderId) as? EKReminder else {
        errorResponse("Reminder not found: \(reminderId)")
    }

    successResponse(["reminder": reminderToDict(reminder)])
}

func createReminder() {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied.")
    }

    // Read JSON from stdin
    let inputData = FileHandle.standardInput.readDataToEndOfFile()
    guard !inputData.isEmpty,
          let json = try? JSONSerialization.jsonObject(with: inputData) as? [String: Any] else {
        errorResponse("Invalid JSON input. Expected: {\"title\": \"...\", \"list\": \"...\", \"due\": \"...\", \"priority\": 0-9}")
    }

    guard let title = json["title"] as? String else {
        errorResponse("Missing required field: title")
    }

    // Find list
    let listName = json["list"] as? String ?? "Reminders"
    let calendars = eventStore.calendars(for: .reminder)
    guard let calendar = calendars.first(where: { $0.title.lowercased() == listName.lowercased() }) ?? eventStore.defaultCalendarForNewReminders() else {
        errorResponse("No reminder lists available")
    }

    // Create reminder
    let reminder = EKReminder(eventStore: eventStore)
    reminder.title = title
    reminder.calendar = calendar

    if let dueStr = json["due"] as? String, let dueDate = parseDate(dueStr) {
        reminder.dueDateComponents = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: dueDate)
    }
    if let priority = json["priority"] as? Int {
        reminder.priority = min(max(priority, 0), 9)
    }
    if let notes = json["notes"] as? String {
        reminder.notes = notes
    }

    do {
        try eventStore.save(reminder, commit: true)
        successResponse([
            "created": true,
            "reminder": reminderToDict(reminder)
        ])
    } catch {
        errorResponse("Failed to create reminder: \(error.localizedDescription)")
    }
}

func completeReminder(reminderId: String) {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied.")
    }

    guard let reminder = eventStore.calendarItem(withIdentifier: reminderId) as? EKReminder else {
        errorResponse("Reminder not found: \(reminderId)")
    }

    reminder.isCompleted = true
    reminder.completionDate = Date()

    do {
        try eventStore.save(reminder, commit: true)
        successResponse([
            "completed": true,
            "reminder": reminderToDict(reminder)
        ])
    } catch {
        errorResponse("Failed to complete reminder: \(error.localizedDescription)")
    }
}

func deleteReminder(reminderId: String) {
    guard requestRemindersAccess() else {
        errorResponse("Reminders access denied.")
    }

    guard let reminder = eventStore.calendarItem(withIdentifier: reminderId) as? EKReminder else {
        errorResponse("Reminder not found: \(reminderId)")
    }

    let reminderTitle = reminder.title ?? "Untitled"

    do {
        try eventStore.remove(reminder, commit: true)
        successResponse([
            "deleted": true,
            "reminderId": reminderId,
            "title": reminderTitle
        ])
    } catch {
        errorResponse("Failed to delete reminder: \(error.localizedDescription)")
    }
}

func printHelp() {
    let help = """
    hestia-reminders-cli - Reminders integration for Hestia

    USAGE:
        hestia-reminders-cli <command> [arguments]

    COMMANDS:
        list-lists                  List all reminder lists
        list-reminders              List reminders (with optional filters)
            --list <name>           Filter by list name
            --completed             Show only completed reminders
            --incomplete            Show only incomplete reminders
        get-reminder <id>           Get details of a specific reminder
        create-reminder             Create a new reminder (reads JSON from stdin)
        complete-reminder <id>      Mark a reminder as complete
        delete-reminder <id>        Delete a reminder
        help, --help, -h            Show this help message

    DATE FORMATS:
        ISO8601: 2025-01-15T10:00:00
        Date only: 2025-01-15
        Keywords: today, tomorrow

    CREATE JSON FORMAT:
        {
            "title": "Buy groceries",
            "list": "Personal",
            "due": "2025-01-15T17:00:00",
            "priority": 1,
            "notes": "Milk, eggs, bread"
        }

    PRIORITY:
        0 = None, 1-4 = High, 5 = Medium, 6-9 = Low

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
case "list-lists":
    listLists()

case "list-reminders":
    listReminders(
        listName: args["list"],
        showCompleted: args["completed"] == "true",
        showIncomplete: args["incomplete"] == "true"
    )

case "get-reminder":
    guard let reminderId = positional.first else {
        errorResponse("Usage: get-reminder <reminder-id>")
    }
    getReminder(reminderId: reminderId)

case "create-reminder":
    createReminder()

case "complete-reminder":
    guard let reminderId = positional.first else {
        errorResponse("Usage: complete-reminder <reminder-id>")
    }
    completeReminder(reminderId: reminderId)

case "delete-reminder":
    guard let reminderId = positional.first else {
        errorResponse("Usage: delete-reminder <reminder-id>")
    }
    deleteReminder(reminderId: reminderId)

case "help", "--help", "-h":
    printHelp()

default:
    errorResponse("Unknown command: \(command). Use --help for usage.")
}
