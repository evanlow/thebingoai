// Raw connector SVG markup keyed by connector id — pair with <ConnectorAvatar
// :db-type :icon-html>. Extracted so pages beyond settings (e.g. the data
// catalog) can render the same connector marks without re-importing the assets.
// ponytail: settings/SettingsConnections.vue still keeps its own inline copy; it
// can adopt this later without any behaviour change.
import connectorPostgres from '~/assets/icons/connector/postgres.svg?raw'
import connectorMysql from '~/assets/icons/connector/mysql.svg?raw'
import connectorDataset from '~/assets/icons/connector/dataset.svg?raw'
import connectorFacebookAds from '~/assets/icons/connector/facebook_ads.svg?raw'
import connectorSqlite from '~/assets/icons/connector/sqlite.svg?raw'
import connectorBigquery from '~/assets/icons/connector/bigquery.svg?raw'
import connectorNotion from '~/assets/icons/connector/notion.svg?raw'
import connectorGoogleSheets from '~/assets/icons/connector/google_sheets.svg?raw'

const connectorIcons: Record<string, string> = {
  postgres: connectorPostgres,
  mysql: connectorMysql,
  dataset: connectorDataset,
  facebook_ads: connectorFacebookAds,
  sqlite: connectorSqlite,
  bigquery_ga4: connectorBigquery,
  notion: connectorNotion,
  google_sheets: connectorGoogleSheets,
}

export function useConnectorIcons() {
  return connectorIcons
}
