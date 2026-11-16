import { describe, it, expect, beforeEach, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PivotConfigPanel from '@/components/pivot/PivotConfigPanel';
import PivotTableRenderer from '@/components/pivot/PivotTableRenderer';
import DrillDownModal from '@/components/pivot/DrillDownModal';
import type { PivotConfigState, AvailableField, PivotData } from '@/types/pivot';
import type { DataSourceDetail } from '@/lib/api';

const mockAvailableFields: AvailableField[] = [
  { name: 'region', type: 'string', sampleValues: ['North', 'South'] },
  { name: 'product', type: 'string', sampleValues: ['A', 'B', 'C'] },
  { name: 'year', type: 'integer', sampleValues: [2024, 2025] },
  { name: 'revenue', type: 'decimal', sampleValues: [1000, 5000, 10000] },
];

const mockSources: DataSourceDetail[] = [
  { id: 1, name: 'Ventes Q1', status: 'completed', source_type: 'csv', row_count: 1200, created_at: '2025-01-01', updated_at: '2025-01-01' } as DataSourceDetail,
];

const mockPivotData: PivotData = {
  pivot: [[1000, 2000], [1500, 2500]],
  row_headers: ['North', 'South'],
  col_headers: ['A', 'B'],
  row_labels: ['region'],
  col_labels: ['product'],
  totals: {
    row_totals: [3000, 4000],
    col_totals: [2500, 4500],
    grand_total: 7000,
  },
  metadata: {
    rows_processed: 100,
    execution_time_ms: 234,
    data_quality_score: 98.5,
  },
  drill_down_available: {
    'row_0_col_0': true,
    'row_0_col_1': true,
    'row_1_col_0': true,
    'row_1_col_1': true,
  },
};

describe('PivotConfigPanel Component', () => {
  const mockConfig: PivotConfigState = {
    sourceId: 1,
    sourceType: 'cleaned',
    rowFields: [],
    columnFields: [],
    valueField: null,
    aggregation: 'sum',
    filters: [],
    includeTotals: true,
    formatCurrency: false,
    sortBy: 'value',
    sortDirection: 'desc',
    topN: null,
  };

  const mockOnConfigChange = vi.fn();
  const mockOnBuild = vi.fn();
  const mockOnSourceChange = vi.fn();

  beforeEach(() => {
    mockOnConfigChange.mockClear();
    mockOnBuild.mockClear();
    mockOnSourceChange.mockClear();
  });

  it('should render configuration panel', () => {
    render(
      <PivotConfigPanel
        config={mockConfig}
        availableFields={mockAvailableFields}
        sources={mockSources}
        onConfigChange={mockOnConfigChange}
        onSourceChange={mockOnSourceChange}
        onBuild={mockOnBuild}
        isLoading={false}
      />
    );

    expect(screen.getByText(/Source de données/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Calculer/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Lancer l'analyse/i)).toBeInTheDocument();
  });

  it('should update config when fields are added', async () => {
    render(
      <PivotConfigPanel
        config={mockConfig}
        availableFields={mockAvailableFields}
        sources={mockSources}
        onConfigChange={mockOnConfigChange}
        onSourceChange={mockOnSourceChange}
        onBuild={mockOnBuild}
        isLoading={false}
      />
    );

    const addButtons = screen.getAllByText(/\+ region/i);
    if (addButtons.length > 0) {
      fireEvent.click(addButtons[0]);
      expect(mockOnConfigChange).toHaveBeenCalled();
    }
  });

  it('should disable build button when config is invalid', () => {
    render(
      <PivotConfigPanel
        config={mockConfig}
        availableFields={mockAvailableFields}
        sources={mockSources}
        onConfigChange={mockOnConfigChange}
        onSourceChange={mockOnSourceChange}
        onBuild={mockOnBuild}
        isLoading={false}
      />
    );

    const buildButton = screen.getByText(/Lancer l'analyse/i);
    expect(buildButton).toBeDisabled();
  });

  it('should enable build button when config is valid', () => {
    const validConfig: PivotConfigState = {
      ...mockConfig,
      sourceId: 1,
      rowFields: ['region'],
      valueField: 'revenue',
    };

    render(
      <PivotConfigPanel
        config={validConfig}
        availableFields={mockAvailableFields}
        sources={mockSources}
        onConfigChange={mockOnConfigChange}
        onSourceChange={mockOnSourceChange}
        onBuild={mockOnBuild}
        isLoading={false}
      />
    );

    const buildButton = screen.getByText(/Lancer l'analyse/i);
    expect(buildButton).not.toBeDisabled();
  });

  it('should call onBuild when build button is clicked', async () => {
    const validConfig: PivotConfigState = {
      ...mockConfig,
      sourceId: 1,
      rowFields: ['region'],
      valueField: 'revenue',
    };

    render(
      <PivotConfigPanel
        config={validConfig}
        availableFields={mockAvailableFields}
        sources={mockSources}
        onConfigChange={mockOnConfigChange}
        onSourceChange={mockOnSourceChange}
        onBuild={mockOnBuild}
        isLoading={false}
      />
    );

    const buildButton = screen.getByText(/Lancer l'analyse/i);
    fireEvent.click(buildButton);

    expect(mockOnBuild).toHaveBeenCalled();
  });
});

describe('PivotTableRenderer Component', () => {
  const mockOnCellClick = vi.fn();

  beforeEach(() => {
    mockOnCellClick.mockClear();
  });

  it('should render pivot table', () => {
    render(<PivotTableRenderer data={mockPivotData} onCellClick={mockOnCellClick} />);
    expect(screen.getByText('North')).toBeInTheDocument();
    expect(screen.getByText('South')).toBeInTheDocument();
  });

  it('should display header row', () => {
    render(<PivotTableRenderer data={mockPivotData} onCellClick={mockOnCellClick} />);
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('should display metadata footer', () => {
    render(<PivotTableRenderer data={mockPivotData} onCellClick={mockOnCellClick} />);
    expect(screen.getByText((content) => content.includes('100'))).toBeInTheDocument();
    expect(screen.getByText(/lignes traitées/)).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes('234'))).toBeInTheDocument();
    expect(screen.getByText(/exécution/)).toBeInTheDocument();
  });

  it('should show empty state', () => {
    const emptyData: PivotData = {
      pivot: [],
      row_headers: [],
      col_headers: [],
      row_labels: [],
      col_labels: [],
      totals: { row_totals: [], col_totals: [], grand_total: 0 },
      metadata: { rows_processed: 0, execution_time_ms: 0, data_quality_score: 0 },
      drill_down_available: {},
    };

    render(<PivotTableRenderer data={emptyData} />);
    expect(screen.getByText(/Aucune donnée/i)).toBeInTheDocument();
  });
});

describe('DrillDownModal Component', () => {
  const mockDrillDownData = {
    success: true,
    rows: [
      { region: 'North', product: 'A', year: 2024, revenue: 500 },
      { region: 'North', product: 'A', year: 2024, revenue: 500 },
    ],
    row_count: 2,
    columns: ['region', 'product', 'year', 'revenue'],
  };

  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    mockOnOpenChange.mockClear();
  });

  it('should render when open', () => {
    render(
      <DrillDownModal
        isOpen={true}
        onOpenChange={mockOnOpenChange}
        data={mockDrillDownData}
      />
    );
    expect(screen.getByText(/Détail.*Cellule/i)).toBeInTheDocument();
  });

  it('should display detail rows', () => {
    render(
      <DrillDownModal
        isOpen={true}
        onOpenChange={mockOnOpenChange}
        data={mockDrillDownData}
      />
    );
    expect(screen.getAllByText('North').length).toBeGreaterThan(0);
    expect(screen.getAllByText('A').length).toBeGreaterThan(0);
    expect(screen.getByText((content) => content.includes('lignes'))).toBeInTheDocument();
  });
});
