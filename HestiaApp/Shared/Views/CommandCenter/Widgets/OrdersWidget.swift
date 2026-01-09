import SwiftUI

/// Widget showing orders list with inline add form
struct OrdersWidget: View {
    @Binding var orders: [Order]
    @Binding var isFormExpanded: Bool

    let onToggleStatus: (UUID) -> Void
    let onDelete: (UUID) -> Void
    let onAddOrder: (Order) -> Void

    var body: some View {
        VStack(spacing: Spacing.md) {
            // Header with add button
            HStack {
                Text("Orders")
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Button {
                    withAnimation(.hestiaStandard) {
                        isFormExpanded.toggle()
                    }
                } label: {
                    HStack(spacing: Spacing.xs) {
                        Image(systemName: isFormExpanded ? "minus" : "plus")
                        Text(isFormExpanded ? "Cancel" : "Add Order")
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.white.opacity(0.7))
                    .padding(.horizontal, Spacing.sm)
                    .padding(.vertical, Spacing.xs)
                    .background(Color.white.opacity(0.1))
                    .cornerRadius(CornerRadius.small)
                }
            }
            .padding(.horizontal, Spacing.lg)

            // Inline Add Form
            if isFormExpanded {
                OrderInlineForm(onSave: { newOrder in
                    onAddOrder(newOrder)
                    withAnimation(.hestiaStandard) {
                        isFormExpanded = false
                    }
                })
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            // Orders List
            if orders.isEmpty && !isFormExpanded {
                emptyState
            } else {
                ForEach(orders) { order in
                    OrderRow(
                        order: order,
                        onToggle: { onToggleStatus(order.id) },
                        onDelete: { onDelete(order.id) }
                    )
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "clock.badge.questionmark")
                .font(.system(size: 32))
                .foregroundColor(.white.opacity(0.3))

            Text("No orders yet")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.5))

            Text("Orders are scheduled prompts that Hestia executes automatically")
                .font(.caption)
                .foregroundColor(.white.opacity(0.3))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }
}

// MARK: - Order Row

struct OrderRow: View {
    let order: Order
    let onToggle: () -> Void
    let onDelete: () -> Void

    @State private var showingDeleteConfirmation = false

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Status indicator
            Button(action: onToggle) {
                Image(systemName: order.orderStatus == .active ? "checkmark.circle.fill" : "pause.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(order.orderStatus == .active ? .healthyGreen : .white.opacity(0.4))
            }

            // Order info
            VStack(alignment: .leading, spacing: 2) {
                Text(order.name)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.white)

                HStack(spacing: Spacing.xs) {
                    // Frequency
                    Text(order.frequency.displayName)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))

                    Text("\u{2022}")
                        .foregroundColor(.white.opacity(0.3))

                    // Resources count
                    Text("\(order.resources.count) resources")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }

                // Last execution status
                if let lastExecution = order.lastExecution {
                    HStack(spacing: 4) {
                        Image(systemName: lastExecution.status.iconName)
                            .font(.caption2)
                            .foregroundColor(statusColor(lastExecution.status))

                        Text(lastExecution.formattedTimestamp)
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.4))
                    }
                }
            }

            Spacer()

            // Delete button
            Button {
                showingDeleteConfirmation = true
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 14))
                    .foregroundColor(.white.opacity(0.3))
            }
        }
        .padding(Spacing.md)
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
        .confirmationDialog("Delete Order?", isPresented: $showingDeleteConfirmation) {
            Button("Delete", role: .destructive) {
                onDelete()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will permanently delete \"\(order.name)\"")
        }
    }

    private func statusColor(_ status: ExecutionStatus) -> Color {
        switch status {
        case .success: return .healthyGreen
        case .failed: return .errorRed
        case .running: return .warningYellow
        case .scheduled: return .white.opacity(0.5)
        }
    }
}

// MARK: - Inline Order Form

struct OrderInlineForm: View {
    let onSave: (Order) -> Void

    @State private var name = ""
    @State private var prompt = ""
    @State private var scheduledTime = Date()
    @State private var frequency: OrderFrequency = .daily
    @State private var customMinutes = 60
    @State private var selectedResources: Set<MCPResource> = []

    @State private var showingCustomFrequency = false

    private var isValid: Bool {
        !name.isEmpty &&
        prompt.count >= 10 &&
        !selectedResources.isEmpty &&
        (frequency != .custom(minutes: 0) || customMinutes >= 15)
    }

    private var validationErrors: [String] {
        var errors: [String] = []
        if name.isEmpty { errors.append("Name is required") }
        if prompt.count < 10 { errors.append("Prompt must be at least 10 characters") }
        if selectedResources.isEmpty { errors.append("Select at least one resource") }
        if case .custom = frequency, customMinutes < 15 {
            errors.append("Custom frequency must be at least 15 minutes")
        }
        return errors
    }

    var body: some View {
        VStack(spacing: Spacing.md) {
            // Name field
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Name")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))

                TextField("Morning Brief", text: $name)
                    .textFieldStyle(OrderTextFieldStyle())
            }

            // Prompt field
            VStack(alignment: .leading, spacing: Spacing.xs) {
                HStack {
                    Text("Prompt")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))

                    Spacer()

                    Text("\(prompt.count)/10 min")
                        .font(.caption2)
                        .foregroundColor(prompt.count >= 10 ? .healthyGreen : .white.opacity(0.4))
                }

                TextEditor(text: $prompt)
                    .font(.body)
                    .foregroundColor(.white)
                    .scrollContentBackground(.hidden)
                    .frame(height: 80)
                    .padding(Spacing.sm)
                    .background(Color.white.opacity(0.1))
                    .cornerRadius(CornerRadius.small)
            }

            // Time and Frequency row
            HStack(spacing: Spacing.md) {
                // Time picker
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Time")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))

                    DatePicker("", selection: $scheduledTime, displayedComponents: .hourAndMinute)
                        .labelsHidden()
                        .colorScheme(.dark)
                }

                // Frequency picker
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Frequency")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))

                    Menu {
                        ForEach([OrderFrequency.once, .daily, .weekly, .monthly], id: \.typeString) { freq in
                            Button(freq.displayName) {
                                frequency = freq
                                showingCustomFrequency = false
                            }
                        }
                        Button("Custom...") {
                            showingCustomFrequency = true
                            frequency = .custom(minutes: customMinutes)
                        }
                    } label: {
                        HStack {
                            Text(frequency.displayName)
                                .foregroundColor(.white)
                            Image(systemName: "chevron.down")
                                .foregroundColor(.white.opacity(0.5))
                        }
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.sm)
                        .background(Color.white.opacity(0.1))
                        .cornerRadius(CornerRadius.small)
                    }
                }
            }

            // Custom frequency stepper
            if showingCustomFrequency {
                HStack {
                    Text("Every")
                        .foregroundColor(.white.opacity(0.7))

                    Stepper("\(customMinutes) minutes", value: $customMinutes, in: 15...1440, step: 15)
                        .labelsHidden()

                    Text("\(customMinutes) minutes")
                        .foregroundColor(.white)
                }
                .padding(Spacing.sm)
                .background(Color.white.opacity(0.05))
                .cornerRadius(CornerRadius.small)
                .onChange(of: customMinutes) { newValue in
                    frequency = .custom(minutes: newValue)
                }
            }

            // Resources
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Resources")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))

                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: Spacing.sm) {
                    ForEach(MCPResource.allCases) { resource in
                        ResourceChip(
                            resource: resource,
                            isSelected: selectedResources.contains(resource),
                            onTap: {
                                if selectedResources.contains(resource) {
                                    selectedResources.remove(resource)
                                } else {
                                    selectedResources.insert(resource)
                                }
                            }
                        )
                    }
                }
            }

            // Validation errors
            if !validationErrors.isEmpty && (!name.isEmpty || !prompt.isEmpty || !selectedResources.isEmpty) {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(validationErrors, id: \.self) { error in
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.errorRed)
                    }
                }
            }

            // Save button
            Button {
                saveOrder()
            } label: {
                Text("Create Order")
                    .font(.buttonText)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(isValid ? Color.white.opacity(0.2) : Color.white.opacity(0.05))
                    .cornerRadius(CornerRadius.button)
            }
            .disabled(!isValid)
        }
        .padding(Spacing.md)
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private func saveOrder() {
        let order = Order(
            id: UUID(),
            name: name,
            prompt: prompt,
            scheduledTime: scheduledTime,
            frequency: frequency,
            resources: selectedResources,
            orderStatus: .active,
            lastExecution: nil,
            createdAt: Date(),
            updatedAt: Date()
        )
        onSave(order)
    }
}

// MARK: - Resource Chip

struct ResourceChip: View {
    let resource: MCPResource
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: Spacing.xs) {
                Image(systemName: resource.iconName)
                    .font(.caption)

                Text(resource.displayName)
                    .font(.caption)
                    .lineLimit(1)
            }
            .foregroundColor(isSelected ? .white : .white.opacity(0.5))
            .padding(.horizontal, Spacing.sm)
            .padding(.vertical, Spacing.xs)
            .background(isSelected ? Color.white.opacity(0.2) : Color.white.opacity(0.05))
            .cornerRadius(CornerRadius.small)
        }
    }
}

// MARK: - Order Text Field Style

struct OrderTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .font(.body)
            .foregroundColor(.white)
            .padding(Spacing.sm)
            .background(Color.white.opacity(0.1))
            .cornerRadius(CornerRadius.small)
    }
}

// MARK: - Preview

struct OrdersWidget_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            ScrollView {
                OrdersWidget(
                    orders: .constant(Order.mockOrders),
                    isFormExpanded: .constant(false),
                    onToggleStatus: { _ in },
                    onDelete: { _ in },
                    onAddOrder: { _ in }
                )
            }
        }
    }
}
