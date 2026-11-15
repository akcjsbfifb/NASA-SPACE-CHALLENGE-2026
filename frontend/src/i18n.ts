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
	weight: string;
	activityLabel: string;
	differsBy: string;
	compare: string;
	reference: string;
	earthColumn: string;
	matchVery: string;
	matchClose: string;
	matchBarely: string;
	scoreHigh: (name: string) => string;
	scoreMid: (name: string) => string;
	scoreLow: (name: string) => string;
	limitations: string;
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
	coverage: string;
	coverageOf: (available: string, total: string) => string;
	worstVariable: string;
	breakdown: string;
	unalikeWarning: string;
	continent: string;
	country: string;
	noCountry: string;
	openOcean: string;
	nearby: string;
	continentNames: Record<string, string>;
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
		objectiveDescription: 'El promedio usa las variables del contrato de análogos. Cada una declara cuánto se puede comparar.',
		slope: 'Pendiente',
		roughness: 'Rugosidad',
		nightTemperature: 'Temperatura nocturna',
		ice: 'Hielo',
		rock: 'Roca',
		weight: 'Peso',
		activityLabel: 'Actividad',
		differsBy: 'Difiere en',
		compare: 'Referencia y Tierra',
		reference: 'Referencia',
		earthColumn: 'Tierra',
		matchVery: 'muy parecido',
		matchClose: 'parecido',
		matchBarely: 'apenas entra',
		scoreHigh: (name: string) => `Se parece en ${name}.`,
		scoreMid: (name: string) => `Se parece a medias en ${name}.`,
		scoreLow: (name: string) => `No se parece en ${name}.`,
		limitations: 'Este porcentaje solo compara las variables de los datasets que entraron en la búsqueda: pendiente, rugosidad, temperatura del mes más frío, espesor de hielo y tipo de roca. No incluye gravedad, atmósfera, vacío ni radiación. Ningún lugar de la Tierra es igual a la Luna. El número es tentativo.',
		precision: 'Precisión',
		morePlaces: 'más lugares',
		morePrecise: 'más precisos',
		searching: 'Buscando...',
		searchAnalogs: 'Buscar análogos',
		initialSummary: 'Elegí los 5 números del sitio lunar y buscá.',
		searchingSummary: 'Buscando en 82 millones de celdas…',
		noResults: (closeness: string) => `Ningún lugar llega a ${closeness}% de similitud. Bajá la precisión.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} lugares distintos, entre ${lowest}% y ${highest}% de similitud.`,
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
		closeness: 'Orden de similitud',
		coverage: 'Cobertura',
		coverageOf: (available: string, total: string) => `${available} de ${total} variables`,
		worstVariable: 'Peor variable',
		breakdown: 'Desglose',
		unalikeWarning: 'Este promedio incluye variables sin equivalencia terrestre validada.',
		continent: 'Continente',
		country: 'País',
		noCountry: 'sin país',
		openOcean: 'océano abierto',
		nearby: 'aproximado',
		continentNames: {
			Africa: 'África',
			Antarctica: 'Antártida',
			Asia: 'Asia',
			Europe: 'Europa',
			'North America': 'América del Norte',
			Oceania: 'Oceanía',
			'South America': 'América del Sur',
			'Seven seas (open ocean)': 'Océano',
		},
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
		objectiveDescription: 'The average uses the variables in the analog contract. Each one declares how comparable it is.',
		slope: 'Slope',
		roughness: 'Roughness',
		nightTemperature: 'Nighttime temperature',
		ice: 'Ice',
		rock: 'Rock',
		weight: 'Weight',
		activityLabel: 'Activity',
		differsBy: 'Differs by',
		compare: 'Reference and Earth',
		reference: 'Reference',
		earthColumn: 'Earth',
		matchVery: 'very close',
		matchClose: 'close',
		matchBarely: 'barely in',
		scoreHigh: (name: string) => `Close on ${name}.`,
		scoreMid: (name: string) => `Only partly close on ${name}.`,
		scoreLow: (name: string) => `Not close on ${name}.`,
		limitations: 'This percentage only compares the dataset variables included in the search: slope, roughness, coldest-month temperature, ice thickness, and rock type. It does not include gravity, atmosphere, vacuum, or radiation. No place on Earth matches the Moon. The number is tentative.',
		precision: 'Precision',
		morePlaces: 'more places',
		morePrecise: 'more precise',
		searching: 'Searching...',
		searchAnalogs: 'Find analogs',
		initialSummary: 'Enter the 5 lunar site measurements and search.',
		searchingSummary: 'Searching 82 million cells…',
		noResults: (closeness: string) => `No locations reach ${closeness}% similarity. Lower the precision.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} distinct locations, between ${lowest}% and ${highest}% similarity.`,
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
		closeness: 'Similarity rank',
		coverage: 'Coverage',
		coverageOf: (available: string, total: string) => `${available} of ${total} variables`,
		worstVariable: 'Worst variable',
		breakdown: 'Breakdown',
		unalikeWarning: 'This average includes variables without a validated terrestrial equivalent.',
		continent: 'Continent',
		country: 'Country',
		noCountry: 'no country',
		openOcean: 'open ocean',
		nearby: 'approximate',
		continentNames: {
			Africa: 'Africa',
			Antarctica: 'Antarctica',
			Asia: 'Asia',
			Europe: 'Europe',
			'North America': 'North America',
			Oceania: 'Oceania',
			'South America': 'South America',
			'Seven seas (open ocean)': 'Ocean',
		},
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
		objectiveDescription: 'La moyenne utilise les variables du contrat d’analogues. Chacune indique son niveau de comparabilité.',
		slope: 'Pente',
		roughness: 'Rugosité',
		nightTemperature: 'Température nocturne',
		ice: 'Glace',
		rock: 'Roche',
		weight: 'Poids',
		activityLabel: 'Activité',
		differsBy: 'Diffère de',
		compare: 'Référence et Terre',
		reference: 'Référence',
		earthColumn: 'Terre',
		matchVery: 'très proche',
		matchClose: 'proche',
		matchBarely: 'tout juste',
		scoreHigh: (name: string) => `Proche pour ${name}.`,
		scoreMid: (name: string) => `Proche en partie pour ${name}.`,
		scoreLow: (name: string) => `Pas proche pour ${name}.`,
		limitations: `Ce pourcentage ne compare que les variables des jeux de données incluses dans la recherche : pente, rugosité, température du mois le plus froid, épaisseur de glace et type de roche. Il n'inclut ni la gravité, ni l'atmosphère, ni le vide, ni le rayonnement. Aucun lieu sur Terre n'égale la Lune. Le nombre est indicatif.`,
		precision: 'Précision',
		morePlaces: 'plus de lieux',
		morePrecise: 'plus précis',
		searching: 'Recherche...',
		searchAnalogs: 'Chercher des analogues',
		initialSummary: 'Saisissez les 5 mesures du site lunaire et lancez la recherche.',
		searchingSummary: 'Recherche parmi 82 millions de cellules…',
		noResults: (closeness: string) => `Aucun lieu n’atteint ${closeness} % de similitude. Réduisez la précision.`,
		resultSummary: (count: number, lowest: string, highest: string) =>
			`${count} lieux distincts, entre ${lowest} % et ${highest} % de similitude.`,
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
		closeness: 'Rang de similitude',
		coverage: 'Couverture',
		coverageOf: (available: string, total: string) => `${available} sur ${total} variables`,
		worstVariable: 'Pire variable',
		breakdown: 'Détail',
		unalikeWarning: 'Cette moyenne inclut des variables sans équivalent terrestre validé.',
		continent: 'Continent',
		country: 'Pays',
		noCountry: 'sans pays',
		openOcean: 'haute mer',
		nearby: 'approximatif',
		continentNames: {
			Africa: 'Afrique',
			Antarctica: 'Antarctique',
			Asia: 'Asie',
			Europe: 'Europe',
			'North America': 'Amérique du Nord',
			Oceania: 'Océanie',
			'South America': 'Amérique du Sud',
			'Seven seas (open ocean)': 'Océan',
		},
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
		objectiveDescription: 'La media usa le variabili del contratto degli analoghi. Ognuna dichiara quanto è comparabile.',
		slope: 'Pendenza',
		roughness: 'Rugosità',
		nightTemperature: 'Temperatura notturna',
		ice: 'Ghiaccio',
		rock: 'Roccia',
		weight: 'Peso',
		activityLabel: 'Attività',
		differsBy: 'Differisce di',
		compare: 'Riferimento e Terra',
		reference: 'Riferimento',
		earthColumn: 'Terra',
		matchVery: 'molto simile',
		matchClose: 'simile',
		matchBarely: 'appena dentro',
		scoreHigh: (name: string) => `Simile per ${name}.`,
		scoreMid: (name: string) => `Simile solo in parte per ${name}.`,
		scoreLow: (name: string) => `Non simile per ${name}.`,
		limitations: 'Questa percentuale confronta solo le variabili dei dataset entrate nella ricerca: pendenza, rugosità, temperatura del mese più freddo, spessore del ghiaccio e tipo di roccia. Non include gravità, atmosfera, vuoto né radiazione. Nessun luogo sulla Terra è uguale alla Luna. Il numero è indicativo.',
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
		closeness: 'Ordine di somiglianza',
		coverage: 'Copertura',
		coverageOf: (available: string, total: string) => `${available} di ${total} variabili`,
		worstVariable: 'Variabile peggiore',
		breakdown: 'Dettaglio',
		unalikeWarning: 'Questa media include variabili senza equivalente terrestre validato.',
		continent: 'Continente',
		country: 'Paese',
		noCountry: 'senza paese',
		openOcean: 'alto mare',
		nearby: 'approssimativo',
		continentNames: {
			Africa: 'Africa',
			Antarctica: 'Antartide',
			Asia: 'Asia',
			Europe: 'Europa',
			'North America': 'America del Nord',
			Oceania: 'Oceania',
			'South America': 'America del Sud',
			'Seven seas (open ocean)': 'Oceano',
		},
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
