<script>
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import * as d3 from 'd3';
	import * as topojson from 'topojson-client';
	import world from 'world-atlas/countries-110m.json';

	let { activeStep = 0 } = $props();

	// Step index is 0-based: 0 = step 1 (exposition), 1 = step 2 (rising action),
	// 2 = step 3 (climax), 3 = step 4 (falling action), 4 = step 5 (resolution).
	const DOTS_STEP = 0;
	const HITS_STEP = 1;
	const CHORO_STEP = 2;
	const TWINS_STEP = 3;
	const FINAL_STEP = 4;

	// Fixed drawing size; the SVG scales to fit the panel via viewBox.
	const width = 960;
	const height = 500;

	const countries = topojson.feature(world, world.objects.countries);
	const projection = d3.geoNaturalEarth1().fitSize([width, height], countries);
	const path = d3.geoPath(projection);
	const featureById = new Map(countries.features.map((f) => [f.id, f]));

	// ---- Steps 1 & 2: dots and local-hit circles ----

	const DOT_RADIUS = 4;
	const DOT_RADIUS_HOVER = 6;
	const MAX_HIT_RADIUS = 28;

	let rows = $state([]); // exposition_countries.csv
	let localHits = $state(new Map()); // iso_numeric -> number of local-hit films

	// One mark per CSV country, placed at the centroid of its matching map shape.
	// The same circle is a dot in step 1 and a sized circle in step 2, so the
	// change between steps animates as one circle growing or shrinking.
	const marks = $derived.by(() => {
		const hitRadius = d3
			.scaleSqrt()
			.domain([0, d3.max(localHits.values()) ?? 1])
			.range([0, MAX_HIT_RADIUS]);

		return rows
			.map((row) => {
				const feature = countries.features.find((f) => f.id === row.iso_numeric);
				if (!feature) return null;
				const [x, y] = path.centroid(feature);
				const hits = localHits.get(row.iso_numeric) ?? 0;
				return { ...row, x, y, hits, hitRadius: hitRadius(hits) };
			})
			.filter(Boolean)
			// Big circles first, so smaller ones are drawn on top and stay hoverable.
			.sort((a, b) => b.hits - a.hits);
	});

	function radius(mark) {
		if (activeStep === DOTS_STEP) {
			return hovered?.iso_numeric === mark.iso_numeric ? DOT_RADIUS_HOVER : DOT_RADIUS;
		}
		if (activeStep === HITS_STEP) return mark.hitRadius; // 0 local hits -> no circle
		return 0; // other steps: circles hidden
	}

	// ---- Step 3: genre choropleth ----

	const MIN_GLOBAL_SHARE = 0.02;
	const LIFT_MIN = 0.25;
	const LIFT_MAX = 4;
	const NO_DATA_FILL = '#3a3a44';

	let genreRows = $state([]); // country_genre_summary.csv
	let isoByIso2 = $state(new Map()); // country_reference.csv: country_iso2 -> iso_numeric
	let selectedGenre = $state('Fantasy');

	// Genres big enough to be meaningful, alphabetical for the dropdown.
	const genres = $derived(
		[
			...new Set(
				genreRows.filter((d) => +d.global_share >= MIN_GLOBAL_SHARE).map((d) => d.genre)
			)
		].sort()
	);

	// iso_numeric -> summary row, for the selected genre only.
	const genreByIso = $derived(
		new Map(
			genreRows
				.filter((d) => d.genre === selectedGenre)
				.map((d) => [isoByIso2.get(d.country_iso2), d])
		)
	);

	// Log scale centred at 1: blue = watches less, neutral = average, red = watches more.
	// RdBu runs red -> blue, so it is reversed to put blue at the low end.
	const color = d3
		.scaleDivergingLog()
		.domain([LIFT_MIN, 1, LIFT_MAX])
		.interpolator((t) => d3.interpolateRdBu(1 - t))
		.clamp(true);

	// Steps 3, 4 and 5 all show the choropleth (4 and 5 keep the genre picked in step 3).
	const showChoropleth = $derived(
		activeStep === CHORO_STEP || activeStep === TWINS_STEP || activeStep === FINAL_STEP
	);

	function countryFill(feature) {
		if (!showChoropleth) return null; // fall back to the plain map colour
		const row = genreByIso.get(feature.id);
		return row ? color(+row.lift) : NO_DATA_FILL;
	}

	// Legend gradient, sampled evenly in log space between the clamp limits.
	const legendGradient = d3
		.range(0, 1.0001, 0.1)
		.map((t) => `${color(LIFT_MIN * (LIFT_MAX / LIFT_MIN) ** t)} ${t * 100}%`)
		.join(', ');

	// ---- Step 4: taste twins ----

	const DEFAULT_COUNTRY = '392'; // Japan

	let profiles = $state(new Map()); // country_profiles.csv: iso_numeric -> row
	let selectedIso = $state(null);

	// Steps 4 and 5 both show the detail card and taste-twin lines.
	const showTwins = $derived(activeStep === TWINS_STEP || activeStep === FINAL_STEP);

	// Step 4 starts on Japan; step 5 starts empty so the reader finds their own country.
	$effect(() => {
		if (activeStep === TWINS_STEP) {
			selectedIso = DEFAULT_COUNTRY;
		} else if (activeStep === FINAL_STEP) {
			selectedIso = null;
			query = '';
			region = 'All';
		}
	});

	const selectedProfile = $derived(profiles.get(selectedIso));
	const selectedFeature = $derived(featureById.get(selectedIso));

	// A curve from a to b that bows upward, so lines don't run along the ground.
	function arc([x1, y1], [x2, y2]) {
		const dx = x2 - x1;
		const dy = y2 - y1;
		const dist = Math.hypot(dx, dy) || 1;
		let nx = -dy / dist;
		let ny = dx / dist;
		if (ny > 0) [nx, ny] = [-nx, -ny];
		const bend = dist * 0.25;
		const cx = (x1 + x2) / 2 + nx * bend;
		const cy = (y1 + y2) / 2 + ny * bend;
		return `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`;
	}

	// The 3 twins, with a line for each one that has a shape on the map.
	const twins = $derived.by(() => {
		if (!selectedProfile) return [];
		const from = selectedFeature ? path.centroid(selectedFeature) : null;
		return [1, 2, 3].map((n) => {
			const iso = selectedProfile[`twin_${n}_iso_numeric`];
			const feature = featureById.get(iso);
			const to = feature ? path.centroid(feature) : null;
			return {
				iso,
				name: selectedProfile[`twin_${n}`],
				similarity: +selectedProfile[`twin_${n}_similarity`],
				farAway: selectedProfile[`twin_${n}_same_region`] === 'False',
				to,
				d: from && to ? arc(from, to) : null
			};
		});
	});

	function onCountryClick(feature) {
		if (!showTwins || !profiles.has(feature.id)) return;
		selectedIso = feature.id;
		query = profiles.get(feature.id).country_name; // keep the step 5 search box in sync
	}

	// ---- Step 5: search and region filter ----

	const REGIONS = ['Africa', 'Americas', 'Asia', 'Europe', 'Oceania', 'All'];

	let query = $state('');
	let region = $state('All');

	const countryNames = $derived(
		[...profiles.values()].map((d) => d.country_name).sort((a, b) => a.localeCompare(b))
	);

	function findByName(name) {
		const q = name.trim().toLowerCase();
		if (!q) return null;
		return [...profiles.values()].find((d) => d.country_name.toLowerCase() === q) ?? null;
	}

	// Select as soon as the text exactly matches a country (e.g. picked from the suggestions).
	function onSearchInput() {
		const match = findByName(query);
		if (match) selectedIso = match.iso_numeric;
	}

	// Enter picks the first country that starts with what was typed.
	function onSearchKeydown(event) {
		if (event.key !== 'Enter') return;
		const q = query.trim().toLowerCase();
		const match =
			findByName(query) ??
			[...profiles.values()].find((d) => d.country_name.toLowerCase().startsWith(q));
		if (q && match) {
			selectedIso = match.iso_numeric;
			query = match.country_name;
		}
	}

	// Dim everything outside the chosen region (countries without data have no region).
	function isDimmed(feature) {
		if (activeStep !== FINAL_STEP || region === 'All') return false;
		return profiles.get(feature.id)?.region !== region;
	}

	// ---- Hover / tooltip ----

	let container;
	let hovered = $state(null);
	let mouse = $state({ x: 0, y: 0 });
	let containerWidth = $state(0);

	// The tooltip content depends on the step, so clear it whenever the step changes.
	$effect(() => {
		activeStep;
		hovered = null;
	});

	function trackMouse(event) {
		const rect = container.getBoundingClientRect();
		mouse = { x: event.clientX - rect.left, y: event.clientY - rect.top };
	}

	function onMarkEnter(event, mark) {
		hovered = mark;
		trackMouse(event);
	}

	function onCountryEnter(event, feature) {
		if (!showChoropleth) return;
		hovered = {
			iso_numeric: feature.id,
			country_name: genreByIso.get(feature.id)?.country_name ?? feature.properties.name
		};
		trackMouse(event);
	}

	// ---- Data loading ----

	onMount(() => {
		// d3.csv keeps every value as a string, so iso_numeric stays e.g. "032".
		const exposition = d3.csv('/data/exposition_countries.csv');

		// Show the step 1 dots as soon as the small file arrives.
		exposition.then((data) => {
			rows = data;
		});

		// Step 3's files are small, so load them straight away too.
		Promise.all([
			d3.csv('/data/country_genre_summary.csv'),
			d3.csv('/data/country_reference.csv')
		]).then(([summary, reference]) => {
			isoByIso2 = new Map(reference.map((d) => [d.country_iso2, d.iso_numeric]));
			genreRows = summary;
		});

		// Step 4: all iso_numeric columns stay strings (d3.csv doesn't convert).
		d3.csv('/data/country_profiles.csv').then((data) => {
			profiles = new Map(data.map((d) => [d.iso_numeric, d]));
		});

		// The enriched file is ~8.7 MB, so step 2's counts fill in when it lands.
		Promise.all([
			exposition,
			d3.csv('/data/film_reach.csv'),
			d3.csv('/data/netflix_2023_films_enriched.csv')
		]).then(([exposition, reach, enriched]) => {
			// A local hit is a film that charted in exactly one country.
			const localTitles = new Set(
				reach.filter((d) => d.n_countries === '1').map((d) => d.show_title)
			);

			// The enriched file has no iso_numeric, so map it via country_iso2.
			const isoNumeric = new Map(exposition.map((d) => [d.country_iso2, d.iso_numeric]));

			// Distinct local-hit titles per country.
			localHits = d3.rollup(
				enriched.filter((d) => localTitles.has(d.show_title)),
				(v) => new Set(v.map((d) => d.show_title)).size,
				(d) => isoNumeric.get(d.country_iso2)
			);
		});
	});
</script>

<div class="map" bind:this={container} bind:clientWidth={containerWidth}>
	{#if activeStep === CHORO_STEP && genres.length}
		<label class="genre-picker" transition:fade={{ duration: 300 }}>
			<span>Genre</span>
			<select bind:value={selectedGenre}>
				{#each genres as genre (genre)}
					<option value={genre}>{genre}</option>
				{/each}
			</select>
		</label>
	{/if}

	<svg viewBox="0 0 {width} {height}" role="img" aria-label="World map of Netflix countries">
		<g class="countries" class:choropleth={showChoropleth}>
			{#each countries.features as feature, i (i)}
				<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
				<path
					d={path(feature)}
					style:fill={countryFill(feature)}
					class:hovered={showChoropleth && hovered?.iso_numeric === feature.id}
					class:clickable={showTwins && profiles.has(feature.id)}
					class:dimmed={isDimmed(feature)}
					onmouseenter={(event) => onCountryEnter(event, feature)}
					onmousemove={trackMouse}
					onmouseleave={() => (hovered = null)}
					onclick={() => onCountryClick(feature)}
				/>
			{/each}
		</g>

		<g class="marks" class:dots={activeStep === DOTS_STEP} class:hits={activeStep === HITS_STEP}>
			{#each marks as mark (mark.iso_numeric)}
				{@const r = radius(mark)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<circle
					cx={mark.x}
					cy={mark.y}
					style:r="{r}px"
					class:hidden={r === 0}
					class:hovered={hovered?.iso_numeric === mark.iso_numeric}
					onmouseenter={(event) => onMarkEnter(event, mark)}
					onmousemove={trackMouse}
					onmouseleave={() => (hovered = null)}
				/>
			{/each}
		</g>

		{#if showTwins && selectedFeature}
			<g class="twins" transition:fade={{ duration: 300 }}>
				<!-- Outline drawn on top so neighbouring countries don't cover it. -->
				<path class="selected-outline" d={path(selectedFeature)} />

				<!-- Re-run the draw-in animation whenever the selection changes. -->
				{#key selectedIso}
					{#each twins.filter((t) => t.d) as twin (twin.iso)}
						<path class="twin-halo" d={twin.d} pathLength="1" />
						<path class="twin-line" class:far={twin.farAway} d={twin.d} pathLength="1" />
						<circle class="twin-end" class:far={twin.farAway} cx={twin.to[0]} cy={twin.to[1]} r="3.5" />
					{/each}
				{/key}
			</g>
		{/if}
	</svg>

	{#if activeStep === FINAL_STEP}
		<div class="finder" transition:fade={{ duration: 300 }}>
			<input
				type="search"
				placeholder="Find your country…"
				aria-label="Find your country"
				list="country-options"
				bind:value={query}
				oninput={onSearchInput}
				onkeydown={onSearchKeydown}
			/>
			<datalist id="country-options">
				{#each countryNames as name (name)}
					<option value={name}></option>
				{/each}
			</datalist>

			<div class="regions" role="group" aria-label="Filter by region">
				{#each REGIONS as r (r)}
					<button
						type="button"
						class:active={region === r}
						aria-pressed={region === r}
						onclick={() => (region = r)}
					>
						{r}
					</button>
				{/each}
			</div>
		</div>

		<p class="closing" transition:fade={{ duration: 300 }}>
			Netflix is global, but taste is still local.
		</p>
	{/if}

	{#if showTwins && selectedProfile}
		<aside class="card" class:below-finder={activeStep === FINAL_STEP} transition:fade={{ duration: 300 }}>
			<p class="card-country">{selectedProfile.country_name}</p>

			<p class="card-label">Top genres</p>
			<ol class="card-genres">
				{#each selectedProfile.top_genres.split('|') as genre (genre)}
					<li>{genre}</li>
				{/each}
			</ol>

			<p class="card-local">
				{Math.round(+selectedProfile.local_film_share * 100)}% of its Top 10 were local films
			</p>

			<p class="card-label">Taste twins</p>
			<ul class="card-twins">
				{#each twins as twin (twin.iso)}
					<li>
						<span class="twin-swatch" class:far={twin.farAway}></span>
						<span class="twin-name">{twin.name}</span>
						<span class="twin-sim">{twin.similarity.toFixed(2)}</span>
					</li>
				{/each}
			</ul>
		</aside>
	{/if}

	{#if showChoropleth}
		<div class="legend" transition:fade={{ duration: 300 }}>
			<div class="legend-bar" style:background="linear-gradient(to right, {legendGradient})"></div>
			<div class="legend-ticks">
				<span>¼×</span>
				<span>1×</span>
				<span>4×</span>
			</div>
			<div class="legend-labels">
				<span>Watches less</span>
				<span>Watches more</span>
			</div>
			<div class="legend-nodata">
				<span class="swatch" style:background={NO_DATA_FILL}></span>
				No data
			</div>
			{#if showTwins && selectedProfile}
				<div class="legend-lines">
					<div><span class="twin-swatch"></span>Taste twin in the same region</div>
					<div><span class="twin-swatch far"></span>Taste twin in another region</div>
				</div>
			{/if}
		</div>
	{/if}

	{#if hovered && activeStep <= FINAL_STEP}
		<!-- Flip to the left of the cursor when near the right edge. -->
		<div
			class="tooltip"
			class:flip={mouse.x > containerWidth * 0.6}
			style:left="{mouse.x}px"
			style:top="{mouse.y}px"
		>
			<p class="country">{hovered.country_name}</p>
			{#if activeStep === DOTS_STEP}
				<p class="film">{hovered.top_film}</p>
				<p class="genres">{hovered.genres.split('|').join(', ')}</p>
				<p class="weeks">
					{hovered.weeks_in_top10}
					{hovered.weeks_in_top10 === '1' ? 'week' : 'weeks'} in the Top 10
				</p>
			{:else if activeStep === HITS_STEP}
				<p class="film">
					{hovered.hits}
					{hovered.hits === 1 ? 'film that was' : 'films that were'} only popular here
				</p>
			{:else}
				{@const row = genreByIso.get(hovered.iso_numeric)}
				<p class="film">{selectedGenre}</p>
				<p class="weeks">
					{row ? `${(+row.lift).toFixed(1)}× the world average` : 'No data'}
				</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.map {
		position: relative;
		width: 100%;
		height: 100%;
	}
	svg {
		display: block;
		width: 100%;
		height: 100%;
	}

	/* Countries: plain map by default, coloured in step 3. */
	.countries path {
		fill: #1f1f27;
		stroke: var(--border);
		stroke-width: 0.5;
		pointer-events: none;
		transition:
			fill 0.6s ease-in-out,
			stroke 0.6s ease-in-out,
			opacity 0.4s ease-in-out;
	}
	.countries.choropleth path {
		stroke: var(--bg);
		pointer-events: auto;
	}
	.countries.choropleth path.hovered {
		stroke: var(--text);
		stroke-width: 1.2;
	}
	.countries.choropleth path.clickable {
		cursor: pointer;
	}
	.countries path {
		opacity: 1;
	}
	.countries path.dimmed {
		opacity: 0.15;
	}

	/* Step 4: selected country and taste-twin lines */
	.twins {
		pointer-events: none;
	}
	.selected-outline {
		fill: none;
		stroke: var(--accent);
		stroke-width: 2;
	}
	.twin-halo,
	.twin-line {
		fill: none;
		stroke-linecap: round;
		stroke-dasharray: 1;
		animation: draw 0.7s ease-out both;
	}
	.twin-halo {
		stroke: var(--bg);
		stroke-width: 4.5;
		stroke-opacity: 0.8;
	}
	.twin-line {
		stroke: var(--text);
		stroke-width: 2;
	}
	.twin-line.far {
		stroke: var(--accent);
	}
	.twin-end {
		fill: var(--text);
		stroke: var(--bg);
		stroke-width: 1.5;
		animation: pop 0.3s 0.6s ease-out both;
	}
	.twin-end.far {
		fill: var(--accent);
	}
	@keyframes draw {
		from {
			stroke-dashoffset: 1;
		}
		to {
			stroke-dashoffset: 0;
		}
	}
	@keyframes pop {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	/* Step 5: search box and region buttons, top of the map */
	.finder {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		z-index: 2;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.finder input {
		width: min(16rem, 100%);
		padding: 0.45rem 0.7rem;
		color: var(--text);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		font: inherit;
		font-size: 0.9rem;
	}
	.finder input:focus-visible {
		border-color: var(--accent);
		outline: none;
	}
	.regions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.regions button {
		padding: 0.3rem 0.7rem;
		color: var(--muted);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 999px;
		font: inherit;
		font-size: 0.8rem;
		cursor: pointer;
		transition:
			color 0.2s,
			border-color 0.2s;
	}
	.regions button:hover,
	.regions button:focus-visible {
		color: var(--text);
		border-color: var(--accent);
		outline: none;
	}
	.regions button.active {
		color: var(--bg);
		background: var(--accent);
		border-color: var(--accent);
	}

	.closing {
		position: absolute;
		right: 0;
		bottom: 0;
		z-index: 1;
		max-width: calc(100% - 17rem);
		margin: 0;
		color: var(--accent);
		font-size: 1rem;
		font-weight: 600;
		text-align: right;
	}

	/* Step 4 detail card, top right of the map */
	.card {
		position: absolute;
		top: 0;
		right: 0;
		z-index: 1;
		width: min(14rem, 45%);
		padding: 0.9rem 1rem;
		background: rgb(22 22 28 / 0.94);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.45);
		font-size: 0.85rem;
		line-height: 1.4;
	}
	/* In step 5 the search box and region buttons sit at the top, so move the card down. */
	.card.below-finder {
		top: 5.5rem;
	}
	.card p {
		margin: 0;
	}
	.card-country {
		color: var(--accent);
		font-size: 0.8rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.card-label {
		margin-top: 0.7rem !important;
		color: var(--muted);
		font-size: 0.7rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.card-genres {
		margin: 0.2rem 0 0;
		padding-left: 1.2rem;
	}
	.card-local {
		margin-top: 0.7rem !important;
		color: var(--muted);
	}
	.card-twins {
		margin: 0.3rem 0 0;
		padding: 0;
		list-style: none;
	}
	.card-twins li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.15rem 0;
	}
	.twin-name {
		flex: 1;
	}
	.twin-sim {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.twin-swatch {
		flex: none;
		display: inline-block;
		width: 1rem;
		height: 2px;
		background: var(--text);
		border-radius: 1px;
	}
	.twin-swatch.far {
		background: var(--accent);
	}

	/* Shared circles: r, fill-opacity and stroke all animate between steps. */
	.marks circle {
		fill: var(--accent);
		fill-opacity: 1;
		stroke: var(--bg);
		stroke-width: 1;
		cursor: pointer;
		transition:
			r 0.8s ease-in-out,
			fill-opacity 0.8s ease-in-out,
			stroke 0.8s ease-in-out;
	}
	.marks circle.hidden {
		pointer-events: none;
	}
	/* Step 1: hover size change should be quick, not the slow step transition. */
	.marks.dots circle.hovered {
		transition: r 0.15s;
	}
	/* Step 2: semi-transparent so overlapping circles in Europe stay readable. */
	.marks.hits circle {
		fill-opacity: 0.35;
		stroke: var(--accent);
	}
	.marks circle.hovered {
		stroke: var(--text);
		stroke-width: 1.5;
	}
	.marks.hits circle.hovered {
		fill-opacity: 0.6;
	}

	/* Step 3 controls */
	.genre-picker {
		position: absolute;
		top: 0;
		left: 0;
		z-index: 1;
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--muted);
		font-size: 0.8rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.genre-picker select {
		padding: 0.4rem 0.6rem;
		color: var(--text);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		font: inherit;
		font-size: 0.9rem;
		letter-spacing: normal;
		text-transform: none;
		cursor: pointer;
	}
	.genre-picker select:hover,
	.genre-picker select:focus-visible {
		border-color: var(--accent);
		outline: none;
	}

	.legend {
		position: absolute;
		bottom: 0;
		left: 0;
		z-index: 1;
		width: min(16rem, 100%);
		color: var(--muted);
		font-size: 0.75rem;
	}
	.legend-bar {
		height: 0.6rem;
		border-radius: 3px;
	}
	.legend-ticks,
	.legend-labels {
		display: flex;
		justify-content: space-between;
		margin-top: 0.25rem;
	}
	.legend-labels {
		color: var(--text);
	}
	.legend-nodata {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.5rem;
	}
	.swatch {
		width: 0.8rem;
		height: 0.8rem;
		border-radius: 2px;
	}
	.legend-lines {
		display: grid;
		gap: 0.3rem;
		margin-top: 0.5rem;
		color: var(--text);
	}
	.legend-lines div {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.tooltip {
		position: absolute;
		z-index: 2;
		max-width: 16rem;
		padding: 0.6rem 0.8rem;
		transform: translate(14px, -50%);
		background: rgb(20 20 24 / 0.95);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
		font-size: 0.85rem;
		line-height: 1.35;
		pointer-events: none;
	}
	.tooltip.flip {
		transform: translate(calc(-100% - 14px), -50%);
	}
	.tooltip p {
		margin: 0;
	}
	.tooltip .country {
		color: var(--accent);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.tooltip .film {
		margin-top: 0.2rem;
		font-weight: 600;
	}
	.tooltip .genres,
	.tooltip .weeks {
		color: var(--muted);
	}
</style>
