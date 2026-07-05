<template>
  <div class="space-y-2">
    <!-- Chart mapping -->
    <template v-if="mapping.type === 'chart' && (mapping.labelColumn || (mapping.datasetColumns?.length ?? 0) > 0 || mapping.xMetricColumn)">
      <div class="text-sm font-medium text-gray-500 uppercase tracking-wide">Column Mapping</div>
      <table class="w-full text-sm">
        <tbody class="divide-y divide-gray-100">
          <tr v-if="mapping.xMetricColumn">
            <td class="py-1 pr-3 text-gray-500 w-24">X Metric</td>
            <td class="py-1 font-mono text-gray-800">{{ mapping.xMetricColumn }}<span v-if="mapping.xAggregation && mapping.xAggregation !== 'none'" class="ml-1 text-gray-400">({{ mapping.xAggregation }})</span></td>
          </tr>
          <tr v-if="mapping.yMetricColumn">
            <td class="py-1 pr-3 text-gray-500">Y Metric</td>
            <td class="py-1 font-mono text-gray-800">{{ mapping.yMetricColumn }}<span v-if="mapping.yAggregation && mapping.yAggregation !== 'none'" class="ml-1 text-gray-400">({{ mapping.yAggregation }})</span></td>
          </tr>
          <tr v-if="mapping.labelColumn">
            <td class="py-1 pr-3 text-gray-500 w-24">Dimension</td>
            <td class="py-1 font-mono text-gray-800">{{ mapping.labelColumn }}</td>
          </tr>
          <tr v-for="ds in (mapping.datasetColumns || [])" :key="ds.column">
            <td class="py-1 pr-3 text-gray-500">Metric "{{ ds.label || ds.column }}"</td>
            <td class="py-1 font-mono text-gray-800">{{ ds.column }}<span v-if="ds.aggregation && ds.aggregation !== 'none'" class="ml-1 text-gray-400">({{ ds.aggregation }})</span></td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- KPI mapping -->
    <template v-else-if="mapping.type === 'kpi' && mapping.valueColumn">
      <div class="text-sm font-medium text-gray-500 uppercase tracking-wide">Column Mapping</div>
      <table class="w-full text-sm">
        <tbody class="divide-y divide-gray-100">
          <tr>
            <td class="py-1 pr-3 text-gray-500 w-32">Main value</td>
            <td class="py-1 font-mono text-gray-800">{{ mapping.valueColumn }}</td>
          </tr>
          <tr v-if="mapping.trendValueColumn">
            <td class="py-1 pr-3 text-gray-500">Trend value</td>
            <td class="py-1 font-mono text-gray-800">{{ mapping.trendValueColumn }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- Table mapping -->
    <template v-else-if="mapping.type === 'table' && (mapping.columnConfig?.length ?? 0) > 0">
      <div class="text-sm font-medium text-gray-500 uppercase tracking-wide">Column Mapping</div>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-400">
            <th class="pb-1 pr-3 text-left font-normal w-32">SQL Column</th>
            <th class="pb-1 pr-3 text-left font-normal">Display Label</th>
            <th class="pb-1 text-left font-normal">Options</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="cc in mapping.columnConfig" :key="cc.column">
            <td class="py-1 pr-3 font-mono text-gray-800">{{ cc.column }}</td>
            <td class="py-1 pr-3 text-gray-700">{{ cc.label }}</td>
            <td class="py-1 text-gray-400">
              <span v-if="cc.sortable" class="mr-1">sortable</span>
              <span v-if="cc.format">{{ cc.format }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { DataSourceMapping } from '~/types/dashboard'

defineProps<{
  mapping: DataSourceMapping
}>()
</script>
