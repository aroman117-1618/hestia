import SwiftUI
import HestiaShared

struct OrdersPanel: View {
    let orders: [OrderResponse]

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header
            HStack {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.textSecondary)
                Text("Active Orders")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                Button {
                    // View all
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Text("View all")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.amberAccent)
                        Image(systemName: "arrow.up.right")
                            .font(.system(size: 11))
                            .foregroundStyle(MacColors.amberAccent)
                    }
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("View all orders")
                .hoverCursor(.pointingHand)
            }

            // Order cards
            if orders.isEmpty {
                VStack(spacing: MacSpacing.sm) {
                    Image(systemName: "bolt.slash")
                        .font(.system(size: 20))
                        .foregroundStyle(MacColors.textSecondary)
                    Text("No active orders")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, MacSpacing.xxl)
            } else {
                VStack(spacing: MacSpacing.sm) {
                    ForEach(orders.prefix(4)) { order in
                        orderCard(order)
                    }
                }
            }
        }
        .padding(MacSpacing.xl)
        .background(MacColors.panelBackground)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    private func orderCard(_ order: OrderResponse) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text(order.name)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Spacer()
                orderStatusBadge(order.status)
            }

            HStack(spacing: MacSpacing.xs) {
                Image(systemName: order.status == .active ? "clock" : "checkmark.circle")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textSecondary)
                Text(order.status == .active ? "Started 45 min ago" : "Finished yesterday")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }

            // Progress bar for running orders
            if order.status == .active {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(MacColors.searchInputBackground)
                            .frame(height: MacSize.orderProgressHeight)
                        RoundedRectangle(cornerRadius: 2)
                            .fill(MacColors.amberAccent)
                            .frame(width: geo.size.width * 0.64, height: MacSize.orderProgressHeight)
                    }
                }
                .frame(height: MacSize.orderProgressHeight)
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func orderStatusBadge(_ status: APIOrderStatus) -> some View {
        let (text, color) = switch status {
        case .active: ("Running", MacColors.healthGreen)
        case .inactive: ("Complete", MacColors.textSecondary)
        }

        return Text(text)
            .font(MacTypography.metadata)
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 3.5)
            .background(color.opacity(0.15))
            .clipShape(Capsule())
    }
}
