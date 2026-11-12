// Approximate exchange rates from the design (1 unit of the currency = `mdl` lei).
// Prices are stored in MDL; other currencies are only for display.
export const RATES_NOTE = 'Cursuri aproximative, fixe, doar pentru orientare. Prețurile reale sunt în MDL.'

export type Region = 'Europa' | 'America' | 'Asia & Pacific' | 'Orientul Mijlociu & Africa'

export interface Currency {
  code: string
  mdl: number
  symbol: string
  iso: string
  region: Region
  label: string
}

const raw: [string, number, string, string, Region, string][] = [
  ['AED', 4.86, 'AED', 'ae', 'Orientul Mijlociu & Africa', 'Dirham EAU'],
  ['ALL', 0.197, 'L', 'al', 'Europa', 'Lek Albanez'],
  ['ARS', 0.018, 'ARS', 'ar', 'America', 'Peso Argentinian'],
  ['AUD', 11.75, 'A$', 'au', 'Asia & Pacific', 'Dolar Australian'],
  ['BAM', 9.94, 'KM', 'ba', 'Europa', 'Marcă Convertibilă'],
  ['BGN', 9.94, 'лв', 'bg', 'Europa', 'Leva Bulgărească'],
  ['BRL', 3.15, 'R$', 'br', 'America', 'Real Brazilian'],
  ['CAD', 12.95, 'CA$', 'ca', 'America', 'Dolar Canadian'],
  ['CHF', 20.4, 'CHF', 'ch', 'Europa', 'Franc Elvețian'],
  ['CLP', 0.019, 'CLP', 'cl', 'America', 'Peso Chilian'],
  ['CNY', 2.48, '¥', 'cn', 'Asia & Pacific', 'Yuan Chinezesc'],
  ['COP', 0.0042, 'COP', 'co', 'America', 'Peso Columbian'],
  ['CZK', 0.77, 'Kč', 'cz', 'Europa', 'Coroană Cehă'],
  ['DKK', 2.61, 'kr', 'dk', 'Europa', 'Coroană Daneză'],
  ['EGP', 0.365, 'E£', 'eg', 'Orientul Mijlociu & Africa', 'Liră Egipteană'],
  ['EUR', 19.45, '€', 'eu', 'Europa', 'Euro'],
  ['GBP', 22.85, '£', 'gb', 'Europa', 'Liră Sterlină'],
  ['GEL', 6.55, '₾', 'ge', 'Europa', 'Lari Georgian'],
  ['HKD', 2.29, 'HK$', 'hk', 'Asia & Pacific', 'Dolar Hong Kong'],
  ['HUF', 0.049, 'Ft', 'hu', 'Europa', 'Forint Maghiar'],
  ['IDR', 0.00114, 'Rp', 'id', 'Asia & Pacific', 'Rupie Indoneziană'],
  ['ILS', 4.82, '₪', 'il', 'Orientul Mijlociu & Africa', 'Șekel Israelian'],
  ['INR', 0.212, '₹', 'in', 'Asia & Pacific', 'Rupie Indiană'],
  ['ISK', 0.13, 'kr', 'is', 'Europa', 'Coroană Islandeză'],
  ['JPY', 0.118, '¥', 'jp', 'Asia & Pacific', 'Yen Japonez'],
  ['KRW', 0.013, '₩', 'kr', 'Asia & Pacific', 'Won Sud-Coreean'],
  ['KWD', 58.2, 'KWD', 'kw', 'Orientul Mijlociu & Africa', 'Dinar Kuweitian'],
  ['KZT', 0.037, '₸', 'kz', 'Asia & Pacific', 'Tenge Kazah'],
  ['MDL', 1, 'lei', 'md', 'Europa', 'Leu Moldovenesc'],
  ['MKD', 0.316, 'ден', 'mk', 'Europa', 'Denar Macedonean'],
  ['MXN', 0.91, 'MX$', 'mx', 'America', 'Peso Mexican'],
  ['MYR', 4.1, 'RM', 'my', 'Asia & Pacific', 'Ringgit Malaezian'],
  ['NOK', 1.66, 'kr', 'no', 'Europa', 'Coroană Norvegiană'],
  ['NZD', 10.75, 'NZ$', 'nz', 'Asia & Pacific', 'Dolar Neozeelandez'],
  ['PEN', 4.75, 'S/', 'pe', 'America', 'Sol Peruvian'],
  ['PHP', 0.31, '₱', 'ph', 'Asia & Pacific', 'Peso Filipinez'],
  ['PLN', 4.52, 'zł', 'pl', 'Europa', 'Zlot Polonez'],
  ['QAR', 4.9, 'QAR', 'qa', 'Orientul Mijlociu & Africa', 'Rial Qatarez'],
  ['RON', 3.91, 'RON', 'ro', 'Europa', 'Leu Românesc'],
  ['RSD', 0.166, 'дин', 'rs', 'Europa', 'Dinar Sârbesc'],
  ['SAR', 4.76, 'SAR', 'sa', 'Orientul Mijlociu & Africa', 'Rial Saudit'],
  ['SEK', 1.71, 'kr', 'se', 'Europa', 'Coroană Suedeză'],
  ['SGD', 13.45, 'S$', 'sg', 'Asia & Pacific', 'Dolar Singaporez'],
  ['THB', 0.53, '฿', 'th', 'Asia & Pacific', 'Baht Thailandez'],
  ['TRY', 0.52, '₺', 'tr', 'Europa', 'Liră Turcească'],
  ['TWD', 0.56, 'NT$', 'tw', 'Asia & Pacific', 'Dolar Taiwanez'],
  ['UAH', 0.432, '₴', 'ua', 'Europa', 'Hrivnă Ucraineană'],
  ['USD', 17.85, '$', 'us', 'America', 'Dolar American'],
  ['VND', 0.00071, '₫', 'vn', 'Asia & Pacific', 'Dong Vietnamez'],
  ['ZAR', 1.01, 'R', 'za', 'Orientul Mijlociu & Africa', 'Rand Sud-African'],
]

export const CURRENCIES: Record<string, Currency> = Object.fromEntries(
  raw.map(([code, mdl, symbol, iso, region, label]) => [code, { code, mdl, symbol, iso, region, label }]),
)
export const CURRENCY_CODES = Object.keys(CURRENCIES).sort()
export const POPULAR = ['EUR', 'USD', 'GBP', 'RON', 'CHF', 'CAD', 'AUD', 'JPY']
export const REGIONS: Region[] = ['Europa', 'America', 'Asia & Pacific', 'Orientul Mijlociu & Africa']

/** Group thousands with a narrow space, like "3 799". */
export function groupThousands(n: number): string {
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function convertFromMdl(mdl: number, code: string): number {
  return mdl / (CURRENCIES[code]?.mdl ?? 1)
}

export function convertToMdl(amount: number, code: string): number {
  return amount * (CURRENCIES[code]?.mdl ?? 1)
}
