/** @jsx jsx */
import { React, Immutable, DataSourceTypes, type IMUseDataSource, jsx } from 'jimu-core';
import { AllWidgetSettingProps } from 'jimu-for-builder';
import { MapWidgetSelector } from 'jimu-ui/advanced/setting-components';
import { DataSourceSelector } from 'jimu-ui/advanced/data-source-selector';
import { SettingSection, SettingRow } from 'jimu-ui/advanced/setting-components';
import { TextInput, Label } from 'jimu-ui';

export default function Setting(props: AllWidgetSettingProps<any>) {
  const onMapSelected = (useMapWidgetIds: string[]) => {
    props.onSettingChange({
      id: props.id,
      useMapWidgetIds
    });
  };

  const onDataSourceChange = (useDataSources: any) => {
    props.onSettingChange({
      id: props.id,
      useDataSources
    });
  };

  const onApiUrlChange = (evt: React.ChangeEvent<HTMLInputElement>) => {
    props.onSettingChange({
      id: props.id,
      config: props.config.set('apiUrl', evt.target.value)
    });
  };

  const onIdFieldChange = (evt: React.ChangeEvent<HTMLInputElement>) => {
    props.onSettingChange({
      id: props.id,
      config: props.config.set('idField', evt.target.value)
    });
  };

  return (
    <div className="widget-setting-smart-spatial-query" style={{ padding: '12px' }}>
      <SettingSection title="Map">
        <SettingRow>
          <MapWidgetSelector
            useMapWidgetIds={props.useMapWidgetIds}
            onSelect={onMapSelected}
          />
        </SettingRow>
      </SettingSection>

      <SettingSection title="Data Source">
        <SettingRow>
          <DataSourceSelector
            useDataSources={props.useDataSources}
            onChange={onDataSourceChange}
            mustUseDataSource
            types={Immutable([DataSourceTypes.FeatureLayer])}
            widgetId={props.id}
          />
        </SettingRow>
      </SettingSection>

      <SettingSection title="API Configuration">
        <SettingRow>
          <Label style={{ display: 'block', marginBottom: '4px' }}>API URL</Label>
          <TextInput
            value={props.config?.apiUrl || ''}
            onChange={onApiUrlChange}
            placeholder="http://127.0.0.1:8000/api/interpret-execute"
          />
        </SettingRow>

        <SettingRow>
          <Label style={{ display: 'block', marginBottom: '4px' }}>ID Field</Label>
          <TextInput
            value={props.config?.idField || ''}
            onChange={onIdFieldChange}
            placeholder="referencenumber"
          />
        </SettingRow>
      </SettingSection>
    </div>
  );
}