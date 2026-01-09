import Foundation
import EventKit

// MARK: - JSON Response Helpers

struct JSONResponse: Encodable {
    let success: Bool
    let data: [String: Any]?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case success, data, error
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encodeIfPresent(error, forKey: .error)
        // Data is encoded separately due to Any type
    }

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
    // Try ISO8601 first
    if let date = isoFormatter.date(from: string) {
        return date
    }
    // Try date-only format
    if let date = dateOnlyFormatter.date(from: string) {
        return date
    }
    // Try "today" keyword
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

func requestCalendarAccess() -> Bool {
    var granted = false
    let semaphore = DispatchSemaphore(value: 0)

    if #available(macOS 14.0, *) {
        eventStore.requestFullAccessToEvents { success, error in
            granted = success
            semaphore.signal()
        }
    } else {
        eventStore.requestAccess(to: .event) { success, error in
            granted = success
            semaphore.signal()
        }
    }

    semaphore.wait()
    return granted
}

func calendarToDict(_ calendar: EKCalendar) -> [String: Any] {
    return [
        "id": calendar.calendarIdentifier,
        "title": calendar.title,
        "type": calendar.type.rawValue,
        "source": calendar.source?.title ?? "Unknown",
        "color": calendar.cgColor?.components?.map { $0 } ?? [],
        "allowsModifications": calendar.allowsContentModifications
    ]
}

func eventToDict(_ event: EKEvent) -> [String: Any] {
    var dict: [String: Any] = [
        "id": event.eventIdentifier ?? "",
        "title": event.title ?? "",
        "calendar": event.calendar?.title ?? "",
        "calendarId": event.calendar?.calendarIdentifier ?? "",
        "isAllDay": event.isAllDay
    ]

    if let start = event.startDate {
        dict["start"] = formatDate(start)
    }
    if let end = event.endDate {
        dict["end"] = formatDate(end)
    }
    if let location = event.location, !location.isEmpty {
        dict["location"] = location
    }
    if let notes = event.notes, !notes.isEmpty {
        dict["notes"] = notes
    }
    if let url = event.url {
        dict["url"] = url.absoluteString
    }

    return dict
}

// MARK: - Commands

func listCalendars() {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied. Please grant access in System Preferences > Privacy & Security > Calendars.")
    }

    let calendars = eventStore.calendars(for: .event)
    let calendarDicts = calendars.map { calendarToDict($0) }

    successResponse([
        "calendars": calendarDicts,
        "count": calendars.count
    ])
}

func listEvents(calendarName: String?, afterDate: String?, beforeDate: String?) {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied. Please grant access in System Preferences > Privacy & Security > Calendars.")
    }

    // Determine date range
    let startDate: Date
    let endDate: Date

    if let after = afterDate, let parsed = parseDate(after) {
        startDate = parsed
    } else {
        // Default: start of today
        startDate = Calendar.current.startOfDay(for: Date())
    }

    if let before = beforeDate, let parsed = parseDate(before) {
        endDate = parsed
    } else {
        // Default: 30 days from start
        endDate = Calendar.current.date(byAdding: .day, value: 30, to: startDate) ?? Date()
    }

    // Get calendars to search
    var calendars: [EKCalendar]
    if let name = calendarName {
        calendars = eventStore.calendars(for: .event).filter { $0.title.lowercased() == name.lowercased() }
        if calendars.isEmpty {
            errorResponse("Calendar '\(name)' not found")
        }
    } else {
        calendars = eventStore.calendars(for: .event)
    }

    // Create predicate and fetch events
    let predicate = eventStore.predicateForEvents(withStart: startDate, end: endDate, calendars: calendars)
    let events = eventStore.events(matching: predicate)

    let eventDicts = events.map { eventToDict($0) }

    successResponse([
        "events": eventDicts,
        "count": events.count,
        "dateRange": [
            "start": formatDate(startDate),
            "end": formatDate(endDate)
        ]
    ])
}

func getEvent(eventId: String) {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied.")
    }

    guard let event = eventStore.event(withIdentifier: eventId) else {
        errorResponse("Event not found: \(eventId)")
    }

    successResponse(["event": eventToDict(event)])
}

func createEvent() {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied.")
    }

    // Read JSON from stdin
    guard let inputData = FileHandle.standardInput.availableData.isEmpty ? nil : FileHandle.standardInput.readDataToEndOfFile(),
          let json = try? JSONSerialization.jsonObject(with: inputData) as? [String: Any] else {
        errorResponse("Invalid JSON input. Expected: {\"title\": \"...\", \"calendar\": \"...\", \"start\": \"...\", \"end\": \"...\"}")
    }

    guard let title = json["title"] as? String else {
        errorResponse("Missing required field: title")
    }

    guard let startStr = json["start"] as? String, let startDate = parseDate(startStr) else {
        errorResponse("Missing or invalid field: start (use ISO8601 format)")
    }

    guard let endStr = json["end"] as? String, let endDate = parseDate(endStr) else {
        errorResponse("Missing or invalid field: end (use ISO8601 format)")
    }

    // Find calendar
    let calendarName = json["calendar"] as? String ?? "Calendar"
    let calendars = eventStore.calendars(for: .event)
    guard let calendar = calendars.first(where: { $0.title.lowercased() == calendarName.lowercased() }) ?? calendars.first else {
        errorResponse("No calendars available")
    }

    // Create event
    let event = EKEvent(eventStore: eventStore)
    event.title = title
    event.startDate = startDate
    event.endDate = endDate
    event.calendar = calendar

    if let location = json["location"] as? String {
        event.location = location
    }
    if let notes = json["notes"] as? String {
        event.notes = notes
    }
    if let isAllDay = json["isAllDay"] as? Bool {
        event.isAllDay = isAllDay
    }

    do {
        try eventStore.save(event, span: .thisEvent)
        successResponse([
            "created": true,
            "event": eventToDict(event)
        ])
    } catch {
        errorResponse("Failed to create event: \(error.localizedDescription)")
    }
}

func updateEvent(eventId: String) {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied.")
    }

    guard let event = eventStore.event(withIdentifier: eventId) else {
        errorResponse("Event not found: \(eventId)")
    }

    // Read JSON from stdin
    guard let inputData = FileHandle.standardInput.availableData.isEmpty ? nil : FileHandle.standardInput.readDataToEndOfFile(),
          let json = try? JSONSerialization.jsonObject(with: inputData) as? [String: Any] else {
        errorResponse("Invalid JSON input")
    }

    // Update fields
    if let title = json["title"] as? String {
        event.title = title
    }
    if let startStr = json["start"] as? String, let startDate = parseDate(startStr) {
        event.startDate = startDate
    }
    if let endStr = json["end"] as? String, let endDate = parseDate(endStr) {
        event.endDate = endDate
    }
    if let location = json["location"] as? String {
        event.location = location
    }
    if let notes = json["notes"] as? String {
        event.notes = notes
    }
    if let calendarName = json["calendar"] as? String {
        if let calendar = eventStore.calendars(for: .event).first(where: { $0.title.lowercased() == calendarName.lowercased() }) {
            event.calendar = calendar
        }
    }

    do {
        try eventStore.save(event, span: .thisEvent)
        successResponse([
            "updated": true,
            "event": eventToDict(event)
        ])
    } catch {
        errorResponse("Failed to update event: \(error.localizedDescription)")
    }
}

func deleteEvent(eventId: String) {
    guard requestCalendarAccess() else {
        errorResponse("Calendar access denied.")
    }

    guard let event = eventStore.event(withIdentifier: eventId) else {
        errorResponse("Event not found: \(eventId)")
    }

    let eventTitle = event.title ?? "Untitled"

    do {
        try eventStore.remove(event, span: .thisEvent)
        successResponse([
            "deleted": true,
            "eventId": eventId,
            "title": eventTitle
        ])
    } catch {
        errorResponse("Failed to delete event: \(error.localizedDescription)")
    }
}

func printHelp() {
    let help = """
    hestia-calendar-cli - Calendar integration for Hestia

    USAGE:
        hestia-calendar-cli <command> [arguments]

    COMMANDS:
        list-calendars              List all available calendars
        list-events                 List events (with optional filters)
            --calendar <name>       Filter by calendar name
            --after <date>          Show events after this date (default: today)
            --before <date>         Show events before this date (default: +30 days)
        get-event <event-id>        Get details of a specific event
        create-event                Create a new event (reads JSON from stdin)
        update-event <event-id>     Update an event (reads JSON from stdin)
        delete-event <event-id>     Delete an event
        help, --help, -h            Show this help message

    DATE FORMATS:
        ISO8601: 2025-01-15T10:00:00
        Date only: 2025-01-15
        Keywords: today, tomorrow

    CREATE/UPDATE JSON FORMAT:
        {
            "title": "Meeting with Bob",
            "calendar": "Work",
            "start": "2025-01-15T10:00:00",
            "end": "2025-01-15T11:00:00",
            "location": "Conference Room A",
            "notes": "Discuss Q1 planning",
            "isAllDay": false
        }

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
case "list-calendars":
    listCalendars()

case "list-events":
    listEvents(
        calendarName: args["calendar"],
        afterDate: args["after"],
        beforeDate: args["before"]
    )

case "get-event":
    guard let eventId = positional.first else {
        errorResponse("Usage: get-event <event-id>")
    }
    getEvent(eventId: eventId)

case "create-event":
    createEvent()

case "update-event":
    guard let eventId = positional.first else {
        errorResponse("Usage: update-event <event-id>")
    }
    updateEvent(eventId: eventId)

case "delete-event":
    guard let eventId = positional.first else {
        errorResponse("Usage: delete-event <event-id>")
    }
    deleteEvent(eventId: eventId)

case "help", "--help", "-h":
    printHelp()

default:
    errorResponse("Unknown command: \(command). Use --help for usage.")
}
