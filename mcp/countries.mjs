// Country geographic filter: axis-aligned boxes, English canonical keys.
// Lookup accepts English and Spanish names (case-insensitive, accents ignored).
function box(latMin, latMax, lonMin, lonMax) {
  return { latMin, latMax, lonMin, lonMax };
}

function normalizeName(name) {
  return String(name)
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/['’.]/g, '')
    .replace(/[-_,]/g, ' ')
    .replace(/\s+/g, ' ');
}

const ARGENTINA_BOX = box(-55.06, -21.78, -73.57, -53.63);

// Axis-aligned boxes only. Canonical key is the English short name.
// Extra aliases: English variants + Spanish common names (normalized at load).
const COUNTRY_ROWS = [
  ['afghanistan', box(29.38, 38.49, 60.5, 74.89), ['afganistan']],
  ['albania', box(39.64, 42.66, 19.26, 21.06), []],
  ['algeria', box(18.96, 37.09, -8.67, 11.98), ['argelia']],
  ['andorra', box(42.43, 42.66, 1.41, 1.79), []],
  ['angola', box(-18.04, -4.37, 11.64, 24.08), []],
  ['antigua and barbuda', box(16.93, 17.73, -62.35, -61.67), ['antigua y barbuda']],
  ['argentina', ARGENTINA_BOX, ['argentine republic', 'republica argentina']],
  ['armenia', box(38.84, 41.3, 43.45, 46.63), ['armenia']],
  ['australia', box(-43.64, -10.06, 113.34, 153.57), ['australia']],
  ['austria', box(46.37, 49.02, 9.53, 17.16), ['austria']],
  ['azerbaijan', box(38.4, 41.91, 44.77, 50.39), ['azerbaiyan']],
  ['bahamas', box(20.91, 27.26, -80.48, -72.71), ['the bahamas', 'bahamas']],
  ['bahrain', box(25.8, 26.29, 50.45, 50.82), ['barein', 'bahrein']],
  ['bangladesh', box(20.74, 26.63, 88.03, 92.67), ['banglades']],
  ['barbados', box(13.04, 13.34, -59.66, -59.42), []],
  ['belarus', box(51.26, 56.17, 23.18, 32.77), ['bielorrusia']],
  ['belgium', box(49.5, 51.51, 2.54, 6.41), ['belgica']],
  ['belize', box(15.89, 18.5, -89.23, -87.48), ['belice']],
  ['benin', box(6.14, 12.42, 0.77, 3.85), ['benin']],
  ['bhutan', box(26.7, 28.36, 88.75, 92.13), ['butan']],
  ['bolivia', box(-22.9, -9.68, -69.64, -57.45), ['plurinational state of bolivia', 'estado plurinacional de bolivia']],
  ['bosnia and herzegovina', box(42.56, 45.28, 15.73, 19.62), ['bosnia y herzegovina', 'bosnia']],
  ['botswana', box(-26.91, -17.78, 19.99, 29.36), ['botsuana']],
  ['brazil', box(-33.75, 5.27, -73.99, -32.39), ['brasil']],
  ['brunei', box(4.0, 5.1, 114.07, 115.36), ['brunei darussalam']],
  ['bulgaria', box(41.24, 44.22, 22.36, 28.61), ['bulgaria']],
  ['burkina faso', box(9.39, 15.08, -5.51, 2.39), []],
  ['burundi', box(-4.47, -2.31, 29.0, 30.85), []],
  ['cabo verde', box(14.8, 17.2, -25.36, -22.67), ['cape verde', 'cabo verde']],
  ['cambodia', box(10.41, 14.69, 102.35, 107.63), ['camboya']],
  ['cameroon', box(1.65, 13.08, 8.49, 16.19), ['camerun']],
  ['canada', box(41.68, 83.11, -141.0, -52.62), ['canada']],
  ['central african republic', box(2.22, 11.0, 14.42, 27.46), ['republica centroafricana']],
  ['chad', box(7.44, 23.45, 13.47, 24.0), ['tchad']],
  ['chile', box(-55.98, -17.5, -75.64, -66.42), ['republica de chile']],
  ['china', box(18.16, 53.56, 73.5, 134.77), ['peoples republic of china', 'republica popular china']],
  ['colombia', box(-4.24, 13.39, -81.73, -66.85), []],
  ['comoros', box(-12.43, -11.36, 43.22, 44.54), ['comoras']],
  ['congo', box(-5.04, 3.71, 11.12, 18.65), ['republic of the congo', 'republica del congo', 'congo brazzaville']],
  ['costa rica', box(8.03, 11.22, -85.95, -82.55), []],
  ['croatia', box(42.4, 46.55, 13.49, 19.43), ['croacia']],
  ['cuba', box(19.83, 23.28, -84.95, -74.13), []],
  ['cyprus', box(34.57, 35.7, 32.27, 34.6), ['chipre']],
  ['czechia', box(48.55, 51.06, 12.09, 18.86), ['czech republic', 'republica checa', 'chequia']],
  ['democratic republic of the congo', box(-13.46, 5.39, 12.2, 31.3), ['drc', 'rdc', 'congo kinshasa', 'republica democratica del congo']],
  ['denmark', box(54.56, 57.75, 8.08, 15.16), ['dinamarca']],
  ['djibouti', box(10.91, 12.71, 41.77, 43.42), ['yibuti']],
  ['dominica', box(15.2, 15.64, -61.48, -61.24), []],
  ['dominican republic', box(17.47, 19.93, -72.0, -68.32), ['republica dominicana']],
  ['ecuador', box(-5.0, 1.68, -81.08, -75.18), []],
  ['egypt', box(21.72, 31.67, 24.7, 36.24), ['egipto']],
  ['el salvador', box(13.16, 14.45, -90.13, -87.69), []],
  ['equatorial guinea', box(-1.46, 3.79, 5.61, 11.33), ['guinea ecuatorial']],
  ['eritrea', box(12.36, 18.0, 36.43, 43.15), []],
  ['estonia', box(57.51, 59.68, 21.76, 28.21), ['estonia']],
  ['eswatini', box(-27.32, -25.72, 30.79, 32.14), ['swaziland', 'suazilandia']],
  ['ethiopia', box(3.4, 14.89, 32.99, 47.99), ['etiopia']],
  ['fiji', box(-21.74, -12.48, 176.81, 180.0), ['fiyi']],
  ['finland', box(59.81, 70.09, 20.55, 31.59), ['finlandia']],
  ['france', box(41.33, 51.09, -5.14, 9.56), ['francia']],
  ['gabon', box(-4.0, 2.32, 8.7, 14.52), ['gabon']],
  ['gambia', box(13.06, 13.83, -16.83, -13.8), ['the gambia']],
  ['georgia', box(41.05, 43.59, 40.01, 46.74), ['georgia']],
  ['germany', box(47.27, 55.06, 5.87, 15.04), ['alemania', 'federal republic of germany']],
  ['ghana', box(4.74, 11.17, -3.24, 1.2), ['ghana']],
  ['greece', box(34.8, 41.75, 19.37, 28.25), ['grecia']],
  ['grenada', box(11.99, 12.53, -61.8, -61.38), ['granada']],
  ['guatemala', box(13.74, 17.82, -92.24, -88.23), []],
  ['guinea', box(7.19, 12.68, -15.08, -7.64), ['guinea conakry']],
  ['guinea bissau', box(10.87, 12.68, -16.72, -13.64), ['guinea-bissau']],
  ['guyana', box(1.18, 8.55, -61.39, -56.47), ['guayana']],
  ['haiti', box(18.02, 20.09, -74.48, -71.62), ['haiti']],
  ['honduras', box(12.98, 16.51, -89.35, -83.13), []],
  ['hungary', box(45.74, 48.59, 16.11, 22.9), ['hungria']],
  ['iceland', box(63.3, 66.54, -24.54, -13.5), ['islandia']],
  ['india', box(6.75, 35.51, 68.11, 97.4), ['india']],
  ['indonesia', box(-11.0, 6.08, 95.01, 141.02), ['indonesia']],
  ['iran', box(25.06, 39.78, 44.03, 63.32), ['iran', 'islamic republic of iran']],
  ['iraq', box(29.06, 37.38, 38.79, 48.57), ['irak']],
  ['ireland', box(51.42, 55.39, -10.48, -5.99), ['irlanda', 'republic of ireland']],
  ['israel', box(29.5, 33.34, 34.27, 35.9), ['israel']],
  ['italy', box(36.62, 47.09, 6.63, 18.52), ['italia']],
  ['ivory coast', box(4.16, 10.74, -8.6, -2.49), ['cote divoire', 'cote d ivoire', 'costa de marfil']],
  ['jamaica', box(17.7, 18.53, -78.37, -76.18), ['jamaica']],
  ['japan', box(24.25, 45.52, 122.93, 145.82), ['japon']],
  ['jordan', box(29.18, 33.38, 34.96, 39.3), ['jordania']],
  ['kazakhstan', box(40.57, 55.44, 46.49, 87.31), ['kazajistan']],
  ['kenya', box(-4.68, 5.51, 33.91, 41.91), ['kenia']],
  ['kiribati', box(-4.7, 4.72, 172.0, 176.84), []],
  ['kuwait', box(28.52, 30.1, 46.55, 48.43), ['kuwait']],
  ['kyrgyzstan', box(39.17, 43.22, 69.46, 80.26), ['kirguistan']],
  ['laos', box(13.91, 22.5, 100.09, 107.64), ['lao', 'laos']],
  ['latvia', box(55.67, 58.08, 20.97, 28.24), ['letonia']],
  ['lebanon', box(33.05, 34.69, 35.1, 36.62), ['libano']],
  ['lesotho', box(-30.68, -28.57, 27.01, 29.46), ['lesoto']],
  ['liberia', box(4.35, 8.55, -11.47, -7.37), []],
  ['libya', box(19.5, 33.17, 9.32, 25.15), ['libia']],
  ['liechtenstein', box(47.05, 47.27, 9.47, 9.64), []],
  ['lithuania', box(53.9, 56.45, 20.94, 26.84), ['lituania']],
  ['luxembourg', box(49.44, 50.18, 5.73, 6.53), ['luxemburgo']],
  ['madagascar', box(-25.61, -11.95, 43.22, 50.48), []],
  ['malawi', box(-17.13, -9.37, 32.67, 35.92), []],
  ['malaysia', box(0.85, 7.36, 99.64, 119.28), ['malasia']],
  ['maldives', box(-0.7, 7.1, 72.69, 73.75), ['maldivas']],
  ['mali', box(10.15, 25.0, -12.24, 4.27), []],
  ['malta', box(35.8, 36.08, 14.18, 14.58), []],
  ['marshall islands', box(4.57, 14.62, 160.79, 172.16), ['islas marshall']],
  ['mauritania', box(14.72, 27.3, -17.07, -4.83), ['mauritania']],
  ['mauritius', box(-20.53, -19.98, 57.3, 57.8), ['mauricio']],
  ['mexico', box(14.53, 32.72, -118.45, -86.7), ['mexico', 'estados unidos mexicanos']],
  ['micronesia', box(5.26, 10.09, 137.42, 163.04), ['federated states of micronesia', 'micronesia']],
  ['moldova', box(45.47, 48.49, 26.62, 30.14), ['moldavia']],
  ['monaco', box(43.72, 43.75, 7.41, 7.44), []],
  ['mongolia', box(41.58, 52.15, 87.75, 119.93), ['mongolia']],
  ['montenegro', box(41.85, 43.56, 18.43, 20.36), ['montenegro']],
  ['morocco', box(21.42, 35.92, -17.02, -0.99), ['marruecos']],
  ['mozambique', box(-26.87, -10.47, 30.21, 40.84), ['mozambique']],
  ['myanmar', box(9.78, 28.54, 92.17, 101.17), ['birmania', 'burma']],
  ['namibia', box(-28.97, -16.96, 11.52, 25.26), ['namibia']],
  ['nauru', box(-0.55, -0.5, 166.91, 166.96), []],
  ['nepal', box(26.35, 30.45, 80.06, 88.2), ['nepal']],
  ['netherlands', box(50.75, 53.55, 3.36, 7.23), ['the netherlands', 'holanda', 'paises bajos']],
  ['new zealand', box(-47.29, -34.39, 166.43, 178.55), ['nueva zelanda', 'nueva zelandia']],
  ['nicaragua', box(10.71, 15.03, -87.69, -83.14), []],
  ['niger', box(11.69, 23.52, 0.16, 15.99), ['niger']],
  ['nigeria', box(4.27, 13.89, 2.67, 14.68), ['nigeria']],
  ['north korea', box(37.67, 43.01, 124.31, 130.7), ['dprk', 'corea del norte', 'democratic peoples republic of korea']],
  ['north macedonia', box(40.85, 42.37, 20.45, 23.03), ['macedonia', 'macedonia del norte']],
  ['norway', box(57.96, 81.03, 4.64, 31.29), ['noruega', 'kingdom of norway', 'reino de noruega']],
  ['oman', box(16.65, 26.39, 52.0, 59.84), ['oman']],
  ['pakistan', box(23.69, 37.1, 60.87, 77.84), ['pakistan']],
  ['palau', box(2.97, 8.09, 131.12, 134.73), ['palaos']],
  ['palestine', box(31.22, 32.55, 34.22, 35.57), ['palestina', 'state of palestine', 'estado de palestina']],
  ['panama', box(7.2, 9.64, -83.05, -77.16), ['panama']],
  ['papua new guinea', box(-11.66, -1.32, 140.84, 159.48), ['papua nueva guinea']],
  ['paraguay', box(-27.61, -19.29, -62.65, -54.26), []],
  ['peru', box(-18.35, -0.04, -81.33, -68.67), ['peru']],
  ['philippines', box(4.64, 21.12, 116.93, 126.6), ['filipinas']],
  ['poland', box(49.0, 54.84, 14.12, 24.15), ['polonia']],
  ['portugal', box(36.96, 42.15, -9.5, -6.19), ['portugal']],
  ['qatar', box(24.48, 26.18, 50.75, 51.61), ['catar']],
  ['romania', box(43.62, 48.27, 20.22, 29.71), ['rumania', 'rumania']],
  ['russia', box(41.19, 81.86, 19.64, 180.0), ['rusia', 'russian federation', 'federacion rusa']],
  ['rwanda', box(-2.84, -1.05, 28.86, 30.9), ['ruanda']],
  ['saint kitts and nevis', box(17.09, 17.42, -62.86, -62.54), ['san cristobal y nieves']],
  ['saint lucia', box(13.7, 14.1, -61.08, -60.87), ['santa lucia']],
  ['saint vincent and the grenadines', box(12.58, 13.38, -61.46, -61.11), ['san vicente y las granadinas']],
  ['samoa', box(-14.05, -13.43, -172.8, -171.41), []],
  ['san marino', box(43.89, 43.99, 12.41, 12.52), []],
  ['sao tome and principe', box(0.02, 1.7, 6.46, 7.46), ['santo tome y principe']],
  ['saudi arabia', box(16.35, 32.15, 34.5, 55.67), ['arabia saudita', 'arabia saudi']],
  ['senegal', box(12.31, 16.69, -17.54, -11.35), ['senegal']],
  ['serbia', box(42.23, 46.19, 18.81, 23.01), ['serbia']],
  ['seychelles', box(-4.8, -3.72, 55.37, 56.28), ['seychelles']],
  ['sierra leone', box(6.92, 10.0, -13.31, -10.27), []],
  ['singapore', box(1.13, 1.47, 103.6, 104.1), ['singapur']],
  ['slovakia', box(47.73, 49.6, 16.83, 22.57), ['eslovaquia']],
  ['slovenia', box(45.42, 46.88, 13.38, 16.61), ['eslovenia']],
  ['solomon islands', box(-11.85, -6.59, 155.51, 169.88), ['islas salomon']],
  ['somalia', box(-1.69, 12.03, 40.98, 51.41), ['somalia']],
  ['south africa', box(-34.83, -22.13, 16.45, 32.89), ['sudafrica', 'republic of south africa', 'rsa']],
  ['south korea', box(33.19, 38.62, 125.89, 129.58), ['korea', 'corea del sur', 'republic of korea', 'corea']],
  ['south sudan', box(3.49, 12.24, 23.44, 35.95), ['sudan del sur']],
  ['spain', box(36.0, 43.79, -9.3, 4.33), ['espana']],
  ['sri lanka', box(5.92, 9.84, 79.65, 81.88), []],
  ['sudan', box(8.68, 22.22, 21.81, 38.58), ['sudan']],
  ['suriname', box(1.83, 6.0, -58.07, -53.98), ['surinam']],
  ['sweden', box(55.34, 69.06, 11.11, 24.17), ['suecia']],
  ['switzerland', box(45.82, 47.81, 5.96, 10.49), ['suiza']],
  ['syria', box(32.31, 37.32, 35.73, 42.38), ['siria', 'syrian arab republic']],
  ['taiwan', box(21.9, 25.3, 119.31, 122.0), ['taiwan', 'republic of china']],
  ['tajikistan', box(36.67, 41.04, 67.39, 75.14), ['tayikistan']],
  ['tanzania', box(-11.76, -0.99, 29.34, 40.45), ['united republic of tanzania']],
  ['thailand', box(5.61, 20.46, 97.34, 105.64), ['tailandia']],
  ['timor leste', box(-9.5, -8.13, 124.04, 127.34), ['east timor', 'timor oriental']],
  ['togo', box(6.1, 11.14, -0.15, 1.81), []],
  ['tonga', box(-21.46, -15.56, -175.68, -173.91), []],
  ['trinidad and tobago', box(10.04, 11.36, -61.93, -60.52), ['trinidad y tobago']],
  ['tunisia', box(30.23, 37.54, 7.52, 11.6), ['tunez']],
  ['turkey', box(35.82, 42.11, 25.67, 44.83), ['turquia', 'turkiye']],
  ['turkmenistan', box(35.14, 42.8, 52.5, 66.68), ['turkmenistan']],
  ['tuvalu', box(-8.55, -5.64, 176.12, 179.86), []],
  ['uganda', box(-1.48, 4.23, 29.57, 35.03), []],
  ['ukraine', box(44.39, 52.38, 22.14, 40.23), ['ucrania']],
  ['united arab emirates', box(22.63, 26.08, 51.58, 56.4), ['uae', 'emiratos arabes unidos']],
  [
    'united kingdom',
    box(49.86, 60.86, -8.65, 1.77),
    ['uk', 'great britain', 'britain', 'reino unido', 'gran bretana', 'inglaterra', 'england'],
  ],
  [
    'united states',
    box(18.91, 71.39, -179.15, -66.95),
    [
      'usa',
      'us',
      'united states of america',
      'estados unidos',
      'eeuu',
      'ee uu',
      'america',
    ],
  ],
  ['uruguay', box(-35.0, -30.09, -58.44, -53.1), []],
  ['uzbekistan', box(37.14, 45.59, 55.99, 73.14), ['uzbekistan']],
  ['vanuatu', box(-20.25, -13.07, 166.52, 170.24), []],
  ['vatican', box(41.9, 41.91, 12.45, 12.46), ['holy see', 'vaticano', 'santa sede']],
  ['venezuela', box(0.63, 12.2, -73.35, -59.8), ['venezuela']],
  ['vietnam', box(8.41, 23.39, 102.14, 109.47), ['viet nam']],
  ['yemen', box(12.11, 18.99, 42.56, 54.53), ['yemen']],
  ['zambia', box(-18.08, -8.22, 21.98, 33.71), []],
  ['zimbabwe', box(-22.42, -15.61, 25.24, 33.06), []],
  ['greenland', box(59.77, 83.63, -73.04, -11.31), ['groenlandia', 'groenlandia']],
  ['puerto rico', box(17.88, 18.52, -67.95, -65.22), []],
  ['antarctica', box(-90.0, -60.0, -180.0, 180.0), ['antartida', 'antartica']],
  ['hong kong', box(22.15, 22.56, 113.84, 114.44), ['hong kong']],
  ['macau', box(22.11, 22.22, 113.53, 113.6), ['macao', 'macau']],
];

const COUNTRY_BOXES = Object.create(null);
const COUNTRY_LOOKUP = new Map();

function addAlias(alias, key) {
  const normalized = normalizeName(alias);
  if (!normalized) return;
  if (!COUNTRY_LOOKUP.has(normalized)) COUNTRY_LOOKUP.set(normalized, key);
}

for (const [key, countryBox, aliases] of COUNTRY_ROWS) {
  COUNTRY_BOXES[key] = countryBox;
  addAlias(key, key);
  for (const alias of aliases) addAlias(alias, key);
}

export function resolveCountry(name) {
  if (typeof name !== 'string') return null;
  return COUNTRY_LOOKUP.get(normalizeName(name)) ?? null;
}

export function getCountryBox(name) {
  const key = resolveCountry(name);
  return key ? COUNTRY_BOXES[key] : null;
}

export { ARGENTINA_BOX, COUNTRY_BOXES, normalizeName };
