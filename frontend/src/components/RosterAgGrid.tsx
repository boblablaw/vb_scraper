"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ColDef,
  FirstDataRenderedEvent,
  ValueFormatterParams,
} from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";

export type RosterRow = {
  id: number;
  name: string;
  position?: string | null;
  classYear?: string | null;
  heightInches?: number | null;
  [key: string]: string | number | null | undefined;
};

const numericColumns = [
  "ms",
  "mp",
  "sp",
  "pts",
  "pts_per_set",
  "k",
  "k_per_set",
  "ae",
  "ta",
  "hit_pct",
  "assists",
  "assists_per_set",
  "sa",
  "sa_per_set",
  "se",
  "digs",
  "digs_per_set",
  "re",
  "tre",
  "rec_pct",
  "bs",
  "ba",
  "tb",
  "blocks_per_set",
  "bhe",
];

const labelMap: Record<string, string> = {
  ms: "MS",
  mp: "MP",
  sp: "SP",
  pts: "PTS",
  pts_per_set: "PTS/S",
  k: "K",
  k_per_set: "K/S",
  ae: "AE",
  ta: "TA",
  hit_pct: "HIT%",
  assists: "A",
  assists_per_set: "A/S",
  sa: "SA",
  sa_per_set: "SA/S",
  se: "SE",
  digs: "D",
  digs_per_set: "D/S",
  re: "RE",
  tre: "TRE",
  rec_pct: "Rec%",
  bs: "BS",
  ba: "BA",
  tb: "TB",
  blocks_per_set: "B/S",
  bhe: "BHE",
};

const formatHeight = ({ value }: ValueFormatterParams): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const inches = Number(value);
  const feet = Math.floor(inches / 12);
  const remainder = inches % 12;
  return `${feet}'${String(remainder).padStart(2, "0")}"`;
};

const formatNumeric = (
  params: ValueFormatterParams,
  header: string,
): string => {
  if (params.value === null || params.value === undefined) {
    return "—";
  }
  const num = Number(params.value);
  if (Number.isNaN(num)) {
    return "—";
  }
  if (header.includes("%")) {
    return `${(num * 100).toFixed(1)}%`;
  }
  if (header.includes("/")) {
    return num.toFixed(2);
  }
  return num.toFixed(0);
};

type Props = {
  rows: RosterRow[];
};

export function RosterAgGrid({ rows }: Props) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const columnDefs = useMemo<ColDef[]>(() => {
    const base: ColDef[] = [
      {
        field: "name",
        headerName: "Name",
        pinned: "left",
        sortable: true,
        filter: "agTextColumnFilter",
        minWidth: 190,
        cellClass: "ag-left-aligned-cell",
      },
      {
        field: "position",
        headerName: "Pos",
        sortable: true,
        filter: "agTextColumnFilter",
        maxWidth: 90,
        cellClass: "ag-center-aligned-cell",
      },
      {
        field: "classYear",
        headerName: "Class",
        sortable: true,
        filter: "agTextColumnFilter",
        maxWidth: 90,
        cellClass: "ag-center-aligned-cell",
      },
      {
        field: "heightInches",
        headerName: "Height",
        sortable: true,
        filter: "agNumberColumnFilter",
        maxWidth: 110,
        cellClass: "ag-center-aligned-cell",
        valueFormatter: formatHeight,
      },
    ];

    const numericDefs = numericColumns.map<ColDef>((colKey) => {
      const header = labelMap[colKey] ?? colKey.toUpperCase();
      return {
        field: colKey,
        headerName: header,
        sortable: true,
        filter: "agNumberColumnFilter",
        width: 80,
        minWidth: 65,
        maxWidth: 110,
        cellClass: "ag-center-aligned-cell",
        valueFormatter: (params) => formatNumeric(params, header),
      };
    });

    return [...base, ...numericDefs];
  }, []);

  const defaultColDef = useMemo<ColDef>(
    () => ({
      resizable: true,
      suppressHeaderMenuButton: false,
      sortable: true,
      filter: true,
      floatingFilter: false,
      menuTabs: ["filterMenuTab"],
    }),
    [],
  );

  const handleFirstDataRendered = useCallback(
    (event: FirstDataRenderedEvent) => {
      const colApi = event.columnApi;
      if (!colApi) return;
      const baseFields = new Set([
        "name",
        "position",
        "classYear",
        "heightInches",
      ]);
      const allColumns = colApi.getAllColumns() ?? [];
      const targetColumns = allColumns.filter((column) => {
        if (!column) return false;
        const colDef = column.getColDef?.();
        const field = colDef?.field;
        return field ? baseFields.has(field) : false;
      });
      if (targetColumns.length > 0) {
        colApi.autoSizeColumns(targetColumns);
      }
    },
    [],
  );

  return (
    <div className="ag-theme-quartz ag-grid-container">
      {mounted ? (
        <AgGridReact
          rowData={rows}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          suppressRowClickSelection
          animateRows
          suppressBrowserResizeObserver
          onFirstDataRendered={handleFirstDataRendered}
          rowHeight={28}
          headerHeight={32}
          domLayout="autoHeight"
        />
      ) : (
        <div className="card">Loading roster...</div>
      )}
    </div>
  );
}

export default RosterAgGrid;
