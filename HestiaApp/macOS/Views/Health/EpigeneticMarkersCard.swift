import SwiftUI
import HestiaShared

struct EpigeneticMarkersCard: View {
    private let genes: [(name: String, description: String)] = [
        ("PON3 Gene", "Paraoxonase 3"),
        ("TNF-a", "Tumor Necrosis Factor-alpha"),
        ("BRCA1 & BRCA2", "Breast Cancer Genes"),
        ("IL-6", "Interleukin-6")
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "dna")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.amberAccent)
                Text("Epigenetic markers")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
            }

            // Histone pill
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textSecondary)
                Text("Histone Modifications Markers")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(.white)
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.innerPillBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
            }

            // 2x2 Gene grid
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: MacSpacing.md) {
                ForEach(genes, id: \.name) { gene in
                    geneItem(name: gene.name, description: gene.description)
                }
            }
        }
        .healthCard()
    }

    private func geneItem(name: String, description: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textSecondary)

            Text(name)
                .font(MacTypography.smallBody)
                .foregroundStyle(.white)
            +
            Text(" (\(description))")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.healthDimText)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.gene)
                .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.gene))
    }
}
