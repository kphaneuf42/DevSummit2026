/** @jsx jsx */
import {
  React, jsx, AllWidgetProps,
  DataSourceManager, QueriableDataSource, FeatureLayerQueryParams
} from 'jimu-core';
import { JimuMapViewComponent, JimuMapView } from 'jimu-arcgis';
import { Button, TextInput, Alert } from 'jimu-ui';
import defaultConfig from '../config';

export default function Widget(props: AllWidgetProps<any>) {
  const [queryText, setQueryText] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [mapView, setMapView] = React.useState<JimuMapView | null>(null);
  const [status, setStatus] = React.useState<string>('Ready');
  const [apiCount, setApiCount] = React.useState<number>(0);
  const [tableCount, setTableCount] = React.useState<number>(0);
  const [selectedCount, setSelectedCount] = React.useState<number>(0);

  const apiUrl = props.config?.apiUrl || defaultConfig.apiUrl;
  const idField = (props.config?.idField || defaultConfig.idField || 'referencenumber').toLowerCase();

  const get311DataSource = (): QueriableDataSource | null => {
    const dsId = props.useDataSources?.[0]?.dataSourceId;
    if (!dsId) return null;
    return DataSourceManager.getInstance().getDataSource(dsId) as QueriableDataSource;
  };

  const quoteSqlString = (v: any) => `'${String(v).replace(/'/g, "''")}'`;

  const buildWhereIn = (fieldLower: string, values: any[]) => {
    // ALWAYS treat ReferenceNumber as string values
    const list = values.map(quoteSqlString).join(',');
    return `${fieldLower} IN (${list})`;
  };

  const applyMapFilter = async (where?: string) => {
    if (!mapView) return;

    const ds = get311DataSource();
    if (!ds) return;

    const view = mapView.view as __esri.MapView;
    await view.when();

    // Try to find the corresponding map feature layer by URL
    const dsLayer = (ds as any).layer as __esri.FeatureLayer | undefined;
    const dsUrl: string | undefined =
      (ds as any)?.url ?? (ds as any)?.layer?.url ?? (dsLayer as any)?.url;

    const allLayers = (view.map as any).allLayers as __esri.Collection<__esri.Layer>;
    const featureLayers = allLayers?.toArray().filter((lyr: any) => lyr?.type === 'feature') as __esri.FeatureLayer[];

    const matches = featureLayers.filter((lyr) => {
      const url = (lyr as any)?.url as string | undefined;
      return dsUrl && url && url.toLowerCase() === dsUrl.toLowerCase();
    });

    // Apply filter if possible
    for (const lyr of matches) {
      try {
        const lv = await view.whenLayerView(lyr) as __esri.FeatureLayerView;
        if (where && where.trim()) {
          lv.filter = { where } as unknown as __esri.FeatureFilter;
        } else {
          (lv as any).filter = null;
        }
      } catch {
        // fallback: definitionExpression
        (lyr as any).definitionExpression = where || '';
      }
    }
  };

  const applyTableFilterIfSupported = async (ds: QueriableDataSource, where: string) => {
    // Experience Builder data sources differ by version/type.
    // We’ll attempt common APIs, but safely no-op if unavailable.
    try {
      // Some DS support updateQueryParams(queryParams, widgetId)
      if (typeof (ds as any).updateQueryParams === 'function') {
        await (ds as any).updateQueryParams({ where }, props.id);
        return true;
      }
      // Some support setQueryParams
      if (typeof (ds as any).setQueryParams === 'function') {
        await (ds as any).setQueryParams({ where }, props.id);
        return true;
      }
    } catch (e) {
      console.warn('applyTableFilterIfSupported failed', e);
    }
    return false;
  };

  const clearAll = async () => {
    const ds = get311DataSource();
    setStatus('Clearing…');
    setApiCount(0);
    setTableCount(0);
    setSelectedCount(0);

    try {
      if (ds) {
        // Clear table filter if possible
        await applyTableFilterIfSupported(ds, '1=1');
        // Clear selection
        await (ds as any).selectRecordsByIds?.([]);
      }
      await applyMapFilter('');
      setStatus('Cleared.');
    } catch (e) {
      console.warn('Clear failed', e);
      setStatus('Cleared (with warnings).');
    }
  };

  const runQuery = async () => {
    if (!apiUrl) {
      setStatus('API URL not set in widget settings.');
      return;
    }
    const ds = get311DataSource();
    if (!ds) {
      setStatus('No data source configured. Choose your 311 layer in widget settings.');
      return;
    }

    setBusy(true);
    setStatus('Calling API…');
    setApiCount(0);
    setTableCount(0);
    setSelectedCount(0);

    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ user_input: queryText })
      });
      const data = await res.json();

      const analysis = data?.analysis || {};

      const startDate = analysis.start_date || "none";
      const endDate = analysis.end_date || "none";
      const bufferDistance = analysis.buffer_distance || "none";

      const features: any[] = Array.isArray(data?.features) ? data.features : [];
      const ids = features
        .map((f: any) => {
          const attrs = f?.attributes || {};
          // normalize keys lower
          const lower: Record<string, any> = {};
          Object.keys(attrs).forEach(k => (lower[k.toLowerCase()] = attrs[k]));
          return lower[idField];
        })
        .filter((v: any) => v !== undefined && v !== null)
        .map((v: any) => String(v)); // FORCE string

      // Dedup IDs (safety)
      const uniq = Array.from(new Set(ids));
      setApiCount(uniq.length);

      if (!uniq.length) {
        setStatus('API returned 0 matches.');
        await applyMapFilter('');
        await applyTableFilterIfSupported(ds, '1=1');
        await (ds as any).selectRecordsByIds?.([]);
        return;
      }

      const where = buildWhereIn(idField, uniq);
      setStatus(`Filtering ${uniq.length} records…`);

      // 1) Filter map
      await applyMapFilter(where);

      // 2) Filter table (if DS supports it)
      const tableFiltered = await applyTableFilterIfSupported(ds, where);

      // 3) Select records (so highlights show)
      // We’ll query DS to get the primary key IDs for selection.
      const schema = ds.getSchema?.();
      const fields = (schema as any)?.fields || {};
      const primaryKey =
        (schema as any)?.primaryKey ||
        Object.keys(fields).find(k => k.toUpperCase() === 'OBJECTID') ||
        'OBJECTID';

      const q: FeatureLayerQueryParams = {
        where,
        outFields: [primaryKey],
        returnGeometry: false
      } as any;

      const queryResult = await (ds as any).query(q);
      const recs: any[] = (queryResult?.records ?? []);

      setTableCount(recs.length);

      const idsToSelect = recs
        .map((r: any) => {
          const rid = r.getId?.();
          if (rid !== undefined && rid !== null) return String(rid);
          const attrs = r.getData?.()?.attributes ?? r.feature?.attributes ?? {};
          return String(attrs[primaryKey]);
        })
        .filter(Boolean);

      // Clear then select (prevents “stuck highlight”)
      await (ds as any).selectRecordsByIds?.([]);
      await (ds as any).selectRecordsByIds?.(idsToSelect);
      setSelectedCount(idsToSelect.length);

      setStatus(
        `Done. Dates: ${startDate} → ${endDate} | Buffer: ${bufferDistance} ft, API=${uniq.length}, Table=${recs.length}, Selected=${idsToSelect.length}` +
        (tableFiltered ? '' : ' (table filter not supported by this DS)')
      );
    } catch (e) {
      console.error('SmartSpatialQuery call failed', e);
      setStatus('Error — see console for details.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="smart-spatial-query p-2" style={{ display: 'grid', gap: 8, width: '100%', minWidth: '500px'}}>
      <Alert form="basic" type="info" text={status} style={{minWidth: '100%' whiteSpace: 'pre-wrap'}}/>

      <div style={{ fontSize: 12 }}>
        API: {apiCount} | Table: {tableCount} | Selected: {selectedCount}
      </div>

      <TextInput
        aria-label="query-text"
        placeholder="Ask a spatial question…"
        value={queryText}
        onChange={(e) => setQueryText(e?.target?.value ?? '')}
        disabled={busy}
      />

      <div style={{ display: 'flex', gap: 8 }}>
        <Button type="primary" onClick={runQuery} disabled={busy}>
          {busy ? 'Running…' : 'Run'}
        </Button>
        <Button onClick={clearAll} disabled={busy}>
          Clear
        </Button>
      </div>

      <JimuMapViewComponent
        useMapWidgetId={props.useMapWidgetIds?.[0]}
        onActiveViewChange={(jmv) => setMapView(jmv)}
      />
    </div>
  );
}