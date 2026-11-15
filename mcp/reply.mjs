export const AUDIENCES = ['profesional', 'aficionado'];
export const LANGUAGES = ['es', 'en', 'fr', 'it'];

const ORDER = ['slope', 'roughness', 'temperature', 'ice', 'rock'];

const CELL = {
  slope: 'slope_deg',
  roughness: 'roughness_m',
  temperature: 'tmin_c',
  ice: 'ice_thickness_m',
  rock: 'rock',
};

const UNIT = {
  slope: 'deg',
  roughness: 'm',
  temperature: 'C',
  ice: 'm',
  rock: 'class',
};

const ROCK_PLAIN = {
  es: { vb: 'basalto', py: 'ceniza volcánica', pb: 'roca profunda', su: 'suelo suelto' },
  en: { vb: 'basalt', py: 'volcanic ash', pb: 'deep rock', su: 'loose soil' },
  fr: { vb: 'basalte', py: 'cendre volcanique', pb: 'roche profonde', su: 'sol meuble' },
  it: { vb: 'basalto', py: 'cenere vulcanica', pb: 'roccia profonda', su: 'suolo sciolto' },
};

const NAMES = {
  es: { slope: 'Pendiente', roughness: 'Rugosidad', temperature: 'Temperatura', ice: 'Hielo', rock: 'Roca' },
  en: { slope: 'Slope', roughness: 'Roughness', temperature: 'Temperature', ice: 'Ice', rock: 'Rock' },
  fr: { slope: 'Pente', roughness: 'Rugosité', temperature: 'Température', ice: 'Glace', rock: 'Roche' },
  it: { slope: 'Pendenza', roughness: 'Rugosità', temperature: 'Temperatura', ice: 'Ghiaccio', rock: 'Roccia' },
};

const LABEL = {
  profesional: NAMES,
  aficionado: NAMES,
};

const AND = { es: 'y', en: 'and', fr: 'et', it: 'e' };

const DIR = {
  es: {
    slope: ['más plana', 'más empinada'],
    roughness: ['por debajo', 'por encima'],
    temperature: ['más fría', 'más cálida'],
    ice: ['más fino', 'más grueso'],
  },
  en: {
    slope: ['flatter', 'steeper'],
    roughness: ['lower', 'higher'],
    temperature: ['colder', 'warmer'],
    ice: ['thinner', 'thicker'],
  },
  fr: {
    slope: ['plus plate', 'plus raide'],
    roughness: ['en dessous', 'au-dessus'],
    temperature: ['plus froide', 'plus chaude'],
    ice: ['plus fine', 'plus épaisse'],
  },
  it: {
    slope: ['più piatta', 'più ripida'],
    roughness: ['più basso', 'più alto'],
    temperature: ['più fredda', 'più calda'],
    ice: ['più sottile', 'più spesso'],
  },
};

function lowerFirst(text) {
  const trimmed = String(text ?? '').trim().replace(/\.$/, '');
  if (!trimmed) return '';
  return trimmed.charAt(0).toLowerCase() + trimmed.slice(1);
}

export function formatNumber(value) {
  const rounded = Math.round(Number(value) * 100) / 100;
  if (Object.is(rounded, -0)) return '0';
  return String(rounded);
}

export function formatSigned(value) {
  const text = formatNumber(value);
  return Number(value) > 0 ? `+${text}` : text;
}

function withUnit(value, unit) {
  const text = typeof value === 'number' ? formatNumber(value) : String(value);
  if (unit === 'deg') return `${text}°`;
  if (unit === 'C') return `${text} °C`;
  if (unit === 'm') return `${text} m`;
  return text;
}

function signedUnit(value, unit) {
  const text = formatSigned(value);
  if (unit === 'deg') return `${text}°`;
  if (unit === 'C') return `${text} °C`;
  if (unit === 'm') return `${text} m`;
  return text;
}

function joinAnd(names, language) {
  if (names.length <= 1) return names[0] ?? '';
  return `${names.slice(0, -1).join(', ')} ${AND[language]} ${names.at(-1)}`;
}

function closestPoint(points) {
  if (!Array.isArray(points) || points.length === 0) return null;
  return points.reduce((best, point) => (
    Number(point?.closeness) > Number(best?.closeness) ? point : best
  ));
}

function onlyActivity(request) {
  const keys = Object.keys(request ?? {}).filter(
    (key) => request[key] !== undefined && request[key] !== null,
  );
  return keys.length === 1 && keys[0] === 'activity';
}

function purposeFor(catalog, activityId, audience, language) {
  const preset = (catalog ?? []).find((entry) => entry.id === activityId);
  if (!preset) return '';
  return preset.voice?.[audience]?.[language] ?? preset.serves?.[language] ?? '';
}

function opening(audience, language, activityId, purpose, request) {
  const aim = lowerFirst(purpose);
  const single = onlyActivity(request) && activityId;
  if (audience === 'aficionado') {
    if (language === 'es') {
      return single
        ? `Pedí la búsqueda con una sola indicación, la actividad ${activityId}. No escribí grados ni tipo de roca: ya venían de misiones anteriores. Sirve para ${aim}.`
        : `La búsqueda usó la actividad ${activityId}. Sirve para ${aim}.`;
    }
    if (language === 'en') {
      return single
        ? `I asked for one search, the activity ${activityId}. I did not type degrees or a rock type: those came from earlier missions. It is for ${aim}.`
        : `The search used the activity ${activityId}. It is for ${aim}.`;
    }
    if (language === 'fr') {
      return single
        ? `J'ai demandé une seule recherche, l'activité ${activityId}. Je n'ai pas écrit de degrés ni de type de roche : ils venaient de missions précédentes. Ça sert à ${aim}.`
        : `La recherche a utilisé l'activité ${activityId}. Ça sert à ${aim}.`;
    }
    return single
      ? `Ho chiesto una sola ricerca, l'attività ${activityId}. Non ho scritto gradi né un tipo di roccia: venivano da missioni precedenti. Serve a ${aim}.`
      : `La ricerca ha usato l'attività ${activityId}. Serve a ${aim}.`;
  }
  if (!activityId) {
    if (language === 'es') return 'La búsqueda usó los valores que mandaste.';
    if (language === 'en') return 'The search used the values you sent.';
    if (language === 'fr') return 'La recherche a utilisé les valeurs envoyées.';
    return 'La ricerca ha usato i valori che hai mandato.';
  }
  if (language === 'es') {
    return single
      ? `Llamé a buscar con un solo argumento: {"activity": "${activityId}"}. No mandé números ni código de roca. Esos valores los puso el preset, para ${aim}.`
      : `La búsqueda usó la actividad ${activityId}. ${purpose}`;
  }
  if (language === 'en') {
    return single
      ? `I called buscar with one argument: {"activity": "${activityId}"}. I sent no numbers and no rock code. The preset filled those values, to ${aim}.`
      : `The search used the activity ${activityId}. ${purpose}`;
  }
  if (language === 'fr') {
    return single
      ? `J'ai appelé buscar avec un seul argument : {"activity": "${activityId}"}. Je n'ai envoyé ni nombres ni code de roche. Le preset a mis ces valeurs, pour ${aim}.`
      : `La recherche a utilisé l'activité ${activityId}. ${purpose}`;
  }
  return single
    ? `Ho chiamato buscar con un solo argomento: {"activity": "${activityId}"}. Non ho mandato numeri né un codice di roccia. Il preset ha messo quei valori, per ${aim}.`
    : `La ricerca ha usato l'attività ${activityId}. ${purpose}`;
}

function usedSentence(labels, audience, language, count) {
  const bits = labels.join(' ');
  if (audience === 'aficionado') {
    if (language === 'es') return `Se miraron ${count} cosas. ${bits}`;
    if (language === 'en') return `It looked at ${count} things. ${bits}`;
    if (language === 'fr') return `Elle a regardé ${count} choses. ${bits}`;
    return `Ha guardato ${count} cose. ${bits}`;
  }
  if (language === 'es') return `Entran ${count} variables. ${bits}`;
  if (language === 'en') return `${count} variables are used. ${bits}`;
  if (language === 'fr') return `${count} variables entrent. ${bits}`;
  return `Entrano ${count} variabili. ${bits}`;
}

function targetBit(label, targetText, audience, language) {
  if (audience === 'aficionado') {
    if (language === 'es') return `${label}, objetivo ${targetText}.`;
    if (language === 'en') return `${label}, target ${targetText}.`;
    if (language === 'fr') return `${label}, objectif ${targetText}.`;
    return `${label}, obiettivo ${targetText}.`;
  }
  if (language === 'es') return `${label}, target ${targetText}.`;
  if (language === 'en') return `${label}, target ${targetText}.`;
  if (language === 'fr') return `${label}, cible ${targetText}.`;
  return `${label}, target ${targetText}.`;
}

function unusedSentence(names, language, temperatureMode) {
  const joined = joinAnd(names, language);
  const mode = temperatureMode === 'not_used' ? ' (temperature_mode: not_used)' : '';
  if (language === 'es') return `${joined} no entran${mode}.`;
  if (language === 'en') return `${joined} are not used${mode}.`;
  if (language === 'fr') return `${joined} n'entrent pas${mode}.`;
  return `${joined} non entrano${mode}.`;
}

function countSentence(audience, language, returned, point) {
  if (!point) {
    if (language === 'es') return `Devolvió ${returned} puntos.`;
    if (language === 'en') return `It returned ${returned} points.`;
    if (language === 'fr') return `Elle a renvoyé ${returned} points.`;
    return `Ha restituito ${returned} punti.`;
  }
  const { lat, lon, closeness } = point;
  if (audience === 'aficionado') {
    if (language === 'es') return `Aparecieron ${returned} lugares. El que más se parece está en lat ${lat}, lon ${lon}. El parecido es ${closeness}.`;
    if (language === 'en') return `${returned} places came back. The closest match is at lat ${lat}, lon ${lon}. The likeness is ${closeness}.`;
    if (language === 'fr') return `${returned} endroits sont sortis. Le plus ressemblant est à lat ${lat}, lon ${lon}. La ressemblance est ${closeness}.`;
    return `Sono usciti ${returned} posti. Quello che somiglia di più è a lat ${lat}, lon ${lon}. La somiglianza è ${closeness}.`;
  }
  if (language === 'es') return `Devolvió ${returned} puntos. El más cercano: lat ${lat}, lon ${lon}, closeness ${closeness}.`;
  if (language === 'en') return `It returned ${returned} points. The closest: lat ${lat}, lon ${lon}, closeness ${closeness}.`;
  if (language === 'fr') return `Elle a renvoyé ${returned} points. Le plus proche : lat ${lat}, lon ${lon}, closeness ${closeness}.`;
  return `Ha restituito ${returned} punti. Il più vicino: lat ${lat}, lon ${lon}, closeness ${closeness}.`;
}

function heading(audience, language) {
  if (audience === 'aficionado') {
    if (language === 'es') return 'En ese lugar, esto es lo que no coincide:';
    if (language === 'en') return 'At that place, this is what does not match:';
    if (language === 'fr') return 'À cet endroit, voilà ce qui ne coïncide pas :';
    return 'In quel posto, ecco cosa non coincide:';
  }
  if (language === 'es') return 'Variables que cambian en ese punto:';
  if (language === 'en') return 'Variables that change at that point:';
  if (language === 'fr') return 'Variables qui changent en ce point :';
  return 'Variabili che cambiano in quel punto:';
}

function plainRock(language, code) {
  return ROCK_PLAIN[language]?.[code] ?? String(code);
}

function changeLine(id, label, target, point, audience, language) {
  const unit = UNIT[id];
  const cell = point?.[CELL[id]];
  const missing = cell === undefined || cell === null || cell === '' || cell === '?';
  const targetText = id === 'rock' ? String(target) : withUnit(target, unit);
  if (missing) {
    if (audience === 'aficionado') {
      const plain = id === 'rock' ? plainRock(language, target) : targetText;
      if (language === 'es') return `${label} no figura: en el dato aparece ?. No se puede decir si es ${plain}.`;
      if (language === 'en') return `${label} is missing: the data shows ?. There is no way to say whether it is ${plain}.`;
      if (language === 'fr') return `${label} ne figure pas : la donnée montre ?. On ne peut pas dire si c'est ${plain}.`;
      return `${label} non c'è: nel dato appare ?. Non si può dire se è ${plain}.`;
    }
    if (language === 'es') return `${label}: target ${targetText}, celda ?. El dato no está, así que no hay cambio numérico.`;
    if (language === 'en') return `${label}: target ${targetText}, cell ?. The value is missing, so there is no numeric change.`;
    if (language === 'fr') return `${label}: cible ${targetText}, cellule ?. La donnée n'est pas là, donc il n'y a pas de changement numérique.`;
    return `${label}: target ${targetText}, cella ?. Il dato non c'è, quindi non c'è un cambiamento numerico.`;
  }
  if (id === 'rock') {
    if (String(cell) === String(target)) {
      if (language === 'es') return `${label}: target ${targetText}, celda ${cell}, cambio 0.`;
      if (language === 'en') return `${label}: target ${targetText}, cell ${cell}, change 0.`;
      if (language === 'fr') return `${label}: cible ${targetText}, cellule ${cell}, changement 0.`;
      return `${label}: target ${targetText}, cella ${cell}, cambiamento 0.`;
    }
    if (audience === 'aficionado') {
      const from = plainRock(language, target);
      const to = plainRock(language, cell);
      if (language === 'es') return `${label} es ${to} en vez de ${from}.`;
      if (language === 'en') return `${label} is ${to} instead of ${from}.`;
      if (language === 'fr') return `${label} est ${to} au lieu de ${from}.`;
      return `${label} è ${to} invece di ${from}.`;
    }
    if (language === 'es') return `${label}: target ${targetText}, celda ${cell}.`;
    if (language === 'en') return `${label}: target ${targetText}, cell ${cell}.`;
    if (language === 'fr') return `${label}: cible ${targetText}, cellule ${cell}.`;
    return `${label}: target ${targetText}, cella ${cell}.`;
  }
  const change = Number(cell) - Number(target);
  const cellText = withUnit(cell, unit);
  const signed = signedUnit(change, unit);
  const abs = withUnit(Math.abs(change), unit);
  if (audience === 'aficionado') {
    if (change === 0) {
      if (language === 'es') return `${label} mide ${cellText}, igual que el objetivo.`;
      if (language === 'en') return `${label} measures ${cellText}, the same as the target.`;
      if (language === 'fr') return `${label} mesure ${cellText}, comme l'objectif.`;
      return `${label} misura ${cellText}, come l'obiettivo.`;
    }
    const dir = DIR[language][id][change < 0 ? 0 : 1];
    if (language === 'es') return `${label} mide ${cellText} en vez de ${targetText}. Quedó ${abs} ${dir}.`;
    if (language === 'en') return `${label} measures ${cellText} instead of ${targetText}. It is ${abs} ${dir}.`;
    if (language === 'fr') return `${label} mesure ${cellText} au lieu de ${targetText}. Ça reste ${abs} ${dir}.`;
    return `${label} misura ${cellText} invece di ${targetText}. Resta ${abs} ${dir}.`;
  }
  const word = language === 'fr' ? 'changement' : language === 'it' ? 'cambiamento' : language === 'en' ? 'change' : 'cambio';
  const cellWord = language === 'fr' ? 'cellule' : language === 'it' ? 'cella' : language === 'en' ? 'cell' : 'celda';
  const targetWord = language === 'fr' ? 'cible' : 'target';
  return `${label}: ${targetWord} ${targetText}, ${cellWord} ${cellText}, ${word} ${signed}.`;
}

export function composeReply(body, context = {}) {
  const language = LANGUAGES.includes(context.language) ? context.language : 'es';
  const audience = AUDIENCES.includes(context.audience) ? context.audience : 'profesional';
  const labels = LABEL[audience][language];
  const target = body?.target ?? {};
  const used = Array.isArray(body?.variables) ? body.variables : [];
  const usedIds = ORDER.filter((id) => used.includes(id));
  const activity = body?.activity;
  const activityId = activity && typeof activity === 'object' ? activity.id : activity;
  const purpose = purposeFor(context.catalog, activityId, audience, language);
  const lines = [opening(audience, language, activityId, purpose, context.request)];
  if (usedIds.length) {
    const bits = usedIds.map((id) => targetBit(
      labels[id],
      id === 'rock' ? String(target[id]) : withUnit(target[id], UNIT[id]),
      audience,
      language,
    ));
    lines.push(usedSentence(bits, audience, language, usedIds.length));
  }
  const unused = ORDER.filter((id) => !used.includes(id)).map((id) => labels[id]);
  if (unused.length) lines.push(unusedSentence(unused, language, body?.temperature_mode));
  const point = closestPoint(body?.points);
  lines.push(countSentence(audience, language, body?.returned ?? 0, point));
  if (point && usedIds.length) {
    const bullets = usedIds
      .map((id) => `- ${changeLine(id, labels[id], target[id], point, audience, language)}`)
      .join('\n');
    lines.push(`${heading(audience, language)}\n\n${bullets}`);
  }
  return lines.filter(Boolean).join('\n\n');
}
