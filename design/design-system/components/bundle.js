/* @ds-bundle: {"format":4,"namespace":"BioSearch","components":[{"name":"SearchBar"},{"name":"FilterChip"},{"name":"Button"},{"name":"ResultCard"},{"name":"PartyTag"},{"name":"MethodTag"},{"name":"Relevance"},{"name":"MetricTile"}]} */
(function () {
  var React = window.React;
  var h = React.createElement;

  function cx() {
    var out = [];
    for (var i = 0; i < arguments.length; i++) if (arguments[i]) out.push(arguments[i]);
    return out.join(' ');
  }
  function omit(props, keys) {
    var rest = {};
    for (var k in props) if (Object.prototype.hasOwnProperty.call(props, k) && keys.indexOf(k) < 0) rest[k] = props[k];
    return rest;
  }

  var PARTIES = {
    D: { key: 'dem', word: 'Democrat' },
    R: { key: 'rep', word: 'Republican' },
    I: { key: 'ind', word: 'Independent' }
  };
  var METHODS = {
    keyword: { label: 'Keyword', detail: 'BM25' },
    semantic: { label: 'Meaning', detail: 'MiniLM' },
    hybrid: { label: 'Hybrid', detail: 'RRF' }
  };
  var GRADES = ['Not relevant', 'Partly relevant', 'Relevant'];

  /* Button: quiet by default; primary (ink) once per view. */
  function Button(props) {
    var variant = props.variant || 'quiet';
    var rest = omit(props, ['variant', 'className', 'children']);
    if (!rest.type) rest.type = 'button';
    rest.className = cx('cb-btn', 'cb-btn-' + variant, props.className);
    return h('button', rest, props.children);
  }

  /* SearchBar: one question in everyday words, one Search button. */
  function SearchBar(props) {
    var label = props.label || 'Search member biographies';
    var input = {
      className: 'cb-search-input',
      type: 'search',
      name: props.name || 'q',
      'aria-label': label,
      placeholder: props.placeholder || 'Ask in everyday words',
      autoComplete: 'off'
    };
    if (props.value !== undefined) {
      input.value = props.value;
      input.onChange = function (e) { if (props.onChange) props.onChange(e.target.value); };
      if (!props.onChange) input.readOnly = true;
    } else {
      if (props.defaultValue !== undefined) input.defaultValue = props.defaultValue;
      if (props.onChange) input.onChange = function (e) { props.onChange(e.target.value); };
    }
    return h('form', {
      className: cx('cb-search', props.className),
      role: 'search',
      onSubmit: function (e) {
        e.preventDefault();
        if (props.onSubmit) props.onSubmit(e.currentTarget.elements[input.name].value);
      }
    },
      h('div', { className: 'cb-search-field' }, h('input', input)),
      h(Button, { variant: 'primary', type: 'submit' }, props.buttonLabel || 'Search'));
  }

  /* FilterChip: a toggle for one chamber, party or state. */
  function FilterChip(props) {
    var rest = omit(props, ['selected', 'count', 'className', 'children']);
    if (!rest.type) rest.type = 'button';
    rest.className = cx('cb-chip', props.className);
    rest['aria-pressed'] = props.selected ? 'true' : 'false';
    return h('button', rest,
      h('span', null, props.children),
      props.count !== undefined && props.count !== null ? h('span', { className: 'cb-chip-count' }, String(props.count)) : null);
  }

  /* PartyTag: the party letter and, unless short, the word. Never colour alone. */
  function PartyTag(props) {
    var p = PARTIES[props.party] || PARTIES.I;
    var letter = PARTIES[props.party] ? props.party : 'I';
    return h('span', { className: cx('cb-party', 'cb-party-' + p.key, props.className), title: props.short ? p.word : undefined },
      h('span', { className: 'cb-party-letter', 'aria-hidden': props.short ? undefined : 'true', 'aria-label': props.short ? p.word : undefined }, letter),
      props.short ? null : h('span', null, p.word));
  }

  /* MethodTag: names one of the three retrieval methods. */
  function MethodTag(props) {
    var key = METHODS[props.method] ? props.method : 'keyword';
    var m = METHODS[key];
    return h('span', { className: cx('cb-method', 'cb-method-' + key, props.className) },
      h('span', null, m.label),
      props.detail === false ? null : h('span', { className: 'cb-method-detail' }, m.detail));
  }

  /* Relevance: the hand label for one judged passage, 0 to 2. */
  function Relevance(props) {
    var g = props.grade === 2 ? 2 : props.grade === 1 ? 1 : 0;
    return h('span', { className: cx('cb-rel', 'cb-rel-' + g, props.className) },
      h('span', { className: 'cb-rel-pips', 'aria-hidden': 'true' },
        h('span', { className: cx('cb-rel-pip', g >= 1 && 'cb-rel-pip-on') }),
        h('span', { className: cx('cb-rel-pip', g >= 2 && 'cb-rel-pip-on') })),
      h('span', null, GRADES[g]));
  }

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/);
    if (!parts[0]) return '';
    var first = parts[0].charAt(0);
    var last = parts.length > 1 ? parts[parts.length - 1].charAt(0) : '';
    return (first + last).toUpperCase();
  }

  /* ResultCard: one ranked passage and the member it is about. */
  function ResultCard(props) {
    var items = [];
    if (props.chamber) items.push(h('span', { key: 'c' }, props.chamber));
    if (props.party) items.push(h(PartyTag, { key: 'p', party: props.party }));
    if (props.state) items.push(h('span', { key: 's' }, props.district ? props.state + ' ' + props.district : props.state));
    var meta = [];
    items.forEach(function (item, i) {
      if (i) meta.push(h('span', { key: 'dot' + i, 'aria-hidden': 'true' }, '\u00b7'));
      meta.push(item);
    });
    var photo = props.photo
      ? h('img', { className: 'cb-result-photo', src: props.photo, alt: 'Portrait of ' + props.name, width: 56, height: 72 })
      : h('div', { className: 'cb-result-photo', 'aria-hidden': 'true' }, initials(props.name));
    return h('article', { className: cx('cb-result', props.className) },
      h('div', { className: 'cb-result-rank', 'aria-label': props.rank !== undefined ? 'Rank ' + props.rank : undefined }, props.rank !== undefined ? props.rank : ''),
      photo,
      h('div', { className: 'cb-result-body' },
        h('h3', { className: 'cb-result-name' }, props.name),
        h('div', { className: 'cb-result-meta' }, meta),
        h('p', { className: 'cb-passage' }, props.children),
        h('div', { className: 'cb-result-foot' },
          props.href ? h('a', { className: 'cb-link', href: props.href, target: '_blank', rel: 'noopener noreferrer' }, 'Read the full article on Wikipedia ↗') : h('span', null),
          props.score !== undefined ? h('span', { className: 'cb-result-score' }, props.score) : null)));
  }

  /* MetricTile: one evaluation metric for one method. */
  function MetricTile(props) {
    return h('div', { className: cx('cb-metric', props.className) },
      h('div', { className: 'cb-metric-label' }, props.label),
      h('div', { className: 'cb-metric-value' }, props.value),
      props.method ? h(MethodTag, { method: props.method, detail: false }) : null,
      props.note ? h('div', { className: 'cb-metric-note' }, props.note) : null);
  }

  window.BioSearch = window.BioSearch || {};
  Object.assign(window.BioSearch, {
    SearchBar: SearchBar,
    FilterChip: FilterChip,
    Button: Button,
    ResultCard: ResultCard,
    PartyTag: PartyTag,
    MethodTag: MethodTag,
    Relevance: Relevance,
    MetricTile: MetricTile
  });
})();
