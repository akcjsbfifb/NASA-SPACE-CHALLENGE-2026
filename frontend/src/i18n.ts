export type Language = 'es' | 'en' | 'fr' | 'it';

type TranslationStrings = {
	language: string;
	pageTitle: string;
	objective: string;
	objectiveDescription: string;
	slope: string;
	roughness: string;
	nightTemperature: string;
	ice: string;
	rock: string;
	precision: string;
	morePlaces: string;
	morePrecise: string;
	searching: string;
	searchAnalogs: string;
	initialSummary: string;
	searchingSummary: string;
	noResults: (closeness: string) => string;
	resultSummary: (count: number, lowest: string, highest: string) => string;
	relativeColdNote: string;
	serverOffline: string;
	searchFailed: string;
	visualizationLayers: string;
	locations: string;
	heatmap: string;
	areas: string;
	labels: string;
	selectedPoint: string;
	latitude: string;
	longitude: string;
	noPointSelected: string;
	point: string;
	close: string;
	noSatelliteImage: string;
	loadingImage: string;
	satelliteView: (latitude: string, longitude: string) => string;
	googleSatellite: string;
	esriSatellite: string;
	viewGoogleMaps: string;
	closeness: string;
	elevation: string;
	coldNight: string;
	noData: string;
	cellError: string;
	nearestCellDistance: (distance: string) => string;
	rocks: Record<string, string>;
};

const translations = {
	es: {
		language: 'Idioma',
		pageTitle: 'ORBITAL',
		objective: 'Objetivo',
		objectiveDescription: 'Ingresar los valores de las 5 medidas del sitio lunar. La cercanía es el promedio de las cinco.',
		slope: 'Pendiente',
		roughness: 'Rugosidad',
		nightTemperature: 'Temperatura nocturna',
		ice: 'Hielo',
		rock: 'Roca',
		precision: 'Precisión',
		morePlaces: 'más lugares',
		morePrecise: 'más precisos',
		searching: 'Buscando...',
		searchAnalogs: 'Buscar análogos',
		initialSummary: 'Elegí los 5 números del sitio lunar y buscá.',
		searchingSummary: 'Buscando en 82 millones de celdas…',
		noResults: (closeness: string) => `Ningún lugar llega a ${closeness}% de cercanía. Bajá la precisión.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} lugares distintos, entre ${lowest}% y ${highest}% de cercanía.`,
		relativeColdNote: ' La temperatura lunar queda fuera del rango terrestre: el puntaje premia el frío relativo.',
		serverOffline: 'No se puede conectar al servidor de búsqueda (puerto 8787). Iniciá el servicio de búsqueda para continuar.',
		searchFailed: 'No se pudo completar la búsqueda.',
		visualizationLayers: 'Capas de visualización',
		locations: 'Ubicaciones',
		heatmap: 'Mapa de calor',
		areas: 'Áreas',
		labels: 'Etiquetas',
		selectedPoint: 'Punto seleccionado',
		latitude: 'Latitud',
		longitude: 'Longitud',
		noPointSelected: 'Ningún punto seleccionado.',
		point: 'PUNTO',
		close: 'Cerrar',
		noSatelliteImage: 'No hay imagen satelital para este punto.',
		loadingImage: 'Cargando imagen…',
		satelliteView: (latitude: string, longitude: string) => `Vista satelital de ${latitude}, ${longitude}`,
		googleSatellite: 'Google Maps · satelital',
		esriSatellite: 'Esri World Imagery · recorte de 800 m',
		viewGoogleMaps: 'Ver en Google Maps',
		closeness: 'Cercanía',
		elevation: 'Elevación',
		coldNight: 'Noche fría',
		noData: 'sin dato',
		cellError: 'No se pudieron cargar los datos de esta celda.',
		nearestCellDistance: (distance: string) => `La celda de tierra más cercana está a ${distance} km del clic.`,
		rocks: {
			vb: 'basalto',
			va: 'volcánico ácido',
			vi: 'volcánico intermedio',
			py: 'piroclástico',
			pb: 'plutónico básico',
			pa: 'plutónico ácido',
			pi: 'plutónico intermedio',
			su: 'sedimento suelto',
			ss: 'sedimentaria',
			sm: 'sedimentaria mixta',
			sc: 'carbonato',
			mt: 'metamórfica',
			ev: 'evaporita',
			ig: 'hielo',
		},
	},
	en: {
		language: 'Language',
		pageTitle: 'ORBITAL',
		objective: 'Target',
		objectiveDescription: 'Five measurements for the lunar site. Closeness is the average of all five.',
		slope: 'Slope',
		roughness: 'Roughness',
		nightTemperature: 'Nighttime temperature',
		ice: 'Ice',
		rock: 'Rock',
		precision: 'Precision',
		morePlaces: 'more places',
		morePrecise: 'more precise',
		searching: 'Searching...',
		searchAnalogs: 'Find analogs',
		initialSummary: 'Enter the 5 lunar site measurements and search.',
		searchingSummary: 'Searching 82 million cells…',
		noResults: (closeness: string) => `No locations reach ${closeness}% closeness. Lower the precision.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} distinct locations, between ${lowest}% and ${highest}% closeness.`,
		relativeColdNote: ' Lunar temperatures are outside the terrestrial range: the score rewards relative cold.',
		serverOffline: 'Cannot connect to the search server (port 8787). Start the search service to continue.',
		searchFailed: 'The search could not be completed.',
		visualizationLayers: 'Visualization layers',
		locations: 'Locations',
		heatmap: 'Heatmap',
		areas: 'Areas',
		labels: 'Labels',
		selectedPoint: 'Selected point',
		latitude: 'Latitude',
		longitude: 'Longitude',
		noPointSelected: 'No point selected.',
		point: 'POINT',
		close: 'Close',
		noSatelliteImage: 'No satellite image is available for this point.',
		loadingImage: 'Loading image…',
		satelliteView: (latitude: string, longitude: string) => `Satellite view of ${latitude}, ${longitude}`,
		googleSatellite: 'Google Maps · satellite',
		esriSatellite: 'Esri World Imagery · 800 m crop',
		viewGoogleMaps: 'View on Google Maps',
		closeness: 'Closeness',
		elevation: 'Elevation',
		coldNight: 'Nighttime low',
		noData: 'no data',
		cellError: 'Could not load data for this cell.',
		nearestCellDistance: (distance: string) => `The nearest land cell is ${distance} km from the click.`,
		rocks: {
			vb: 'basalt',
			va: 'acidic volcanic',
			vi: 'intermediate volcanic',
			py: 'pyroclastic',
			pb: 'basic plutonic',
			pa: 'acidic plutonic',
			pi: 'intermediate plutonic',
			su: 'loose sediment',
			ss: 'sedimentary',
			sm: 'mixed sedimentary',
			sc: 'carbonate',
			mt: 'metamorphic',
			ev: 'evaporite',
			ig: 'ice',
		},
	},
	fr: {
		language: 'Langue',
		pageTitle: 'ORBITAL',
		objective: 'Objectif',
		objectiveDescription: 'Cinq mesures du site lunaire. La proximité est la moyenne des cinq.',
		slope: 'Pente',
		roughness: 'Rugosité',
		nightTemperature: 'Température nocturne',
		ice: 'Glace',
		rock: 'Roche',
		precision: 'Précision',
		morePlaces: 'plus de lieux',
		morePrecise: 'plus précis',
		searching: 'Recherche...',
		searchAnalogs: 'Chercher des analogues',
		initialSummary: 'Saisissez les 5 mesures du site lunaire et lancez la recherche.',
		searchingSummary: 'Recherche parmi 82 millions de cellules…',
		noResults: (closeness: string) => `Aucun lieu n’atteint ${closeness} % de proximité. Réduisez la précision.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} lieux distincts, entre ${lowest} % et ${highest} % de proximité.`,
		relativeColdNote: ' Les températures lunaires dépassent la plage terrestre : le score favorise le froid relatif.',
		serverOffline: 'Impossible de joindre le serveur de recherche (port 8787). Démarrez le service de recherche pour continuer.',
		searchFailed: 'La recherche n’a pas pu aboutir.',
		visualizationLayers: 'Couches de visualisation',
		locations: 'Emplacements',
		heatmap: 'Carte thermique',
		areas: 'Zones',
		labels: 'Étiquettes',
		selectedPoint: 'Point sélectionné',
		latitude: 'Latitude',
		longitude: 'Longitude',
		noPointSelected: 'Aucun point sélectionné.',
		point: 'POINT',
		close: 'Fermer',
		noSatelliteImage: 'Aucune image satellite disponible pour ce point.',
		loadingImage: 'Chargement de l’image…',
		satelliteView: (latitude: string, longitude: string) => `Vue satellite de ${latitude}, ${longitude}`,
		googleSatellite: 'Google Maps · satellite',
		esriSatellite: 'Esri World Imagery · extrait de 800 m',
		viewGoogleMaps: 'Voir sur Google Maps',
		closeness: 'Proximité',
		elevation: 'Altitude',
		coldNight: 'Minimum nocturne',
		noData: 'aucune donnée',
		cellError: 'Impossible de charger les données de cette cellule.',
		nearestCellDistance: (distance: string) => `La cellule terrestre la plus proche se trouve à ${distance} km du clic.`,
		rocks: {
			vb: 'basalte',
			va: 'volcanique acide',
			vi: 'volcanique intermédiaire',
			py: 'pyroclastique',
			pb: 'plutonique basique',
			pa: 'plutonique acide',
			pi: 'plutonique intermédiaire',
			su: 'sédiment meuble',
			ss: 'sédimentaire',
			sm: 'sédimentaire mixte',
			sc: 'carbonate',
			mt: 'métamorphique',
			ev: 'évaporite',
			ig: 'glace',
		},
	},
	it: {
		language: 'Lingua',
		pageTitle: 'ORBITAL',
		objective: 'Obiettivo',
		objectiveDescription: 'Cinque misure del sito lunare. La somiglianza è la media delle cinque.',
		slope: 'Pendenza',
		roughness: 'Rugosità',
		nightTemperature: 'Temperatura notturna',
		ice: 'Ghiaccio',
		rock: 'Roccia',
		precision: 'Precisione',
		morePlaces: 'più luoghi',
		morePrecise: 'più precisi',
		searching: 'Ricerca...',
		searchAnalogs: 'Cerca analoghi',
		initialSummary: 'Inserisci i 5 valori del sito lunare e avvia la ricerca.',
		searchingSummary: 'Ricerca in 82 milioni di celle…',
		noResults: (closeness: string) => `Nessun luogo raggiunge il ${closeness}% di somiglianza. Riduci la precisione.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} luoghi distinti, tra il ${lowest}% e il ${highest}% di somiglianza.`,
		relativeColdNote: ' Le temperature lunari sono fuori dall’intervallo terrestre: il punteggio premia il freddo relativo.',
		serverOffline: 'Impossibile raggiungere il server di ricerca (porta 8787). Avvia il servizio di ricerca per continuare.',
		searchFailed: 'Impossibile completare la ricerca.',
		visualizationLayers: 'Livelli di visualizzazione',
		locations: 'Posizioni',
		heatmap: 'Mappa di calore',
		areas: 'Aree',
		labels: 'Etichette',
		selectedPoint: 'Punto selezionato',
		latitude: 'Latitudine',
		longitude: 'Longitudine',
		noPointSelected: 'Nessun punto selezionato.',
		point: 'PUNTO',
		close: 'Chiudi',
		noSatelliteImage: 'Nessuna immagine satellitare disponibile per questo punto.',
		loadingImage: 'Caricamento immagine…',
		satelliteView: (latitude: string, longitude: string) => `Vista satellitare di ${latitude}, ${longitude}`,
		googleSatellite: 'Google Maps · satellite',
		esriSatellite: 'Esri World Imagery · ritaglio di 800 m',
		viewGoogleMaps: 'Apri in Google Maps',
		closeness: 'Somiglianza',
		elevation: 'Elevazione',
		coldNight: 'Minima notturna',
		noData: 'nessun dato',
		cellError: 'Impossibile caricare i dati di questa cella.',
		nearestCellDistance: (distance: string) => `La cella terrestre più vicina è a ${distance} km dal clic.`,
		rocks: {
			vb: 'basalto',
			va: 'vulcanica acida',
			vi: 'vulcanica intermedia',
			py: 'piroclastica',
			pb: 'plutonica basica',
			pa: 'plutonica acida',
			pi: 'plutonica intermedia',
			su: 'sedimento sciolto',
			ss: 'sedimentaria',
			sm: 'sedimentaria mista',
			sc: 'carbonato',
			mt: 'metamorfica',
			ev: 'evaporite',
			ig: 'ghiaccio',
		},
	},
} satisfies Record<Language, TranslationStrings>;

export function getCopy(language: Language): TranslationStrings {
	return translations[language];
}

export function isLanguage(value: string): value is Language {
	return value === 'es' || value === 'en' || value === 'fr' || value === 'it';
}
