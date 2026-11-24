<script>
	import * as d3 from 'd3';
	import { Tween, prefersReducedMotion } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	/**
	 * @typedef {{ title: string, year: number, likes: number, views: number, revenue: number }} Film
	 * @typedef {'likes' | 'views'} Metric
	 * @type {{ films: Film[], metric?: Metric }}
	 */
	let { films, metric = 'likes' } = $props();

	let width = $state(0);
	let height = $state(0);

	const margin = { top: 16, right: 24, bottom: 52, left: 72 };

	let innerW = $derived(Math.max(0, width - margin.left - margin.right));
	let innerH = $derived(Math.max(0, height - margin.top - margin.bottom));

	// Square-root scales from 0: big gaps between films stay visible (unlike log),
	// while small values still get more room than on a linear scale.
	/** @param {Metric} key */
	const xScale = (key) =>
		d3
			.scaleSqrt()
			.domain([0, d3.max(films, (d) => d[key]) ?? 1])
			.nice()
			.range([0, innerW]);
	let xLikes = $derived(xScale('likes'));
	let xViews = $derived(xScale('views'));
	let y = $derived(
		d3
			.scaleSqrt()
			.domain([0, d3.max(films, (d) => d.revenue) ?? 1])
			.nice()
			.range([innerH, 0])
	);

	// 0 = likes on the x-axis, 1 = views. Tweening it slides the dots between the two
	// positions and cross-fades the two sets of x ticks. No animation for reduced motion.
	const mix = new Tween(metric === 'views' ? 1 : 0, { duration: 500, easing: cubicOut });
	$effect(() => {
		mix.set(metric === 'views' ? 1 : 0, { duration: prefersReducedMotion.current ? 0 : 500 });
	});
	/** @param {Film} d */
	const px = (d) => (1 - mix.current) * xLikes(d.likes) + mix.current * xViews(d.views);

	// Hand-picked ticks: a square-root axis stretches the low end, so evenly spaced
	// ticks (0, 1M, 2M …) would leave the crowded lower-left with no reference lines.
	const LIKES_TICKS = [0, 10e3, 100e3, 250e3, 500e3, 1e6, 2e6, 3e6, 4e6, 5e6];
	const VIEWS_TICKS = [0, 1e6, 10e6, 25e6, 50e6, 100e6, 200e6, 300e6, 400e6];
	const Y_TICKS = [0, 10e6, 100e6, 250e6, 500e6, 1e9, 1.5e9, 2e9, 2.5e9, 3e9, 3.5e9];
	/** The ticks that fall inside the scale's domain. */
	const ticks = (scale, list) => list.filter((t) => t <= scale.domain()[1]);
	let xAxes = $derived([
		{ key: 'likes', scale: xLikes, ticks: LIKES_TICKS, opacity: 1 - mix.current },
		{ key: 'views', scale: xViews, ticks: VIEWS_TICKS, opacity: mix.current }
	]);

	// 1000 -> 1K, 2_000_000 -> 2M, 3e9 -> 3B (d3's SI format says "G" for billions).
	const si = d3.format('~s');
	const short = (n) => si(n).replace('k', 'K').replace('G', 'B');
	const fmtDollars = (n) => '$' + short(n);
	const fmtFull = d3.format(',');
	const fmtDollarsFull = (n) => '$' + d3.format(',.3~s')(n).replace('k', 'K').replace('G', 'B');

	// Name the films at the four extremes (for the metric on the x-axis), each placed in
	// empty space next to its dot. The film with the fewest likes/views sits inside the
	// busy lower-left cluster, so its label goes in the empty area to the right on a
	// leader line (`at` is [fraction of plot width, revenue]).
	/** @typedef {{ film: Film, dx: number, dy: number, anchor: string, at?: [number, number] }} Label */
	let labelled = $derived.by(() => {
		if (!films.length) return [];
		const most = d3.greatest(films, (d) => d[metric]);
		const fewest = d3.least(films, (d) => d[metric]);
		const richest = d3.greatest(films, (d) => d.revenue);
		const poorest = d3.least(films, (d) => d.revenue);
		/** @type {Map<Film, Omit<Label, 'film'>>} */
		const placed = new Map();
		placed.set(richest, { dx: -10, dy: 4, anchor: 'end' });
		if (!placed.has(most)) placed.set(most, { dx: -8, dy: -10, anchor: 'end' });
		if (!placed.has(fewest)) placed.set(fewest, { dx: 0, dy: 0, anchor: 'start', at: [0.26, 60e6] });
		if (!placed.has(poorest)) placed.set(poorest, { dx: 10, dy: 4, anchor: 'start' });
		return [...placed].map(([film, pos]) => ({ film, ...pos }));
	});
	let extremes = $derived(new Set(labelled.map((l) => l.film)));

	/** @type {Film | null} */
	let hovered = $state(null);
</script>

<div class="chart" bind:clientWidth={width} bind:clientHeight={height}>
	{#if innerW > 0 && innerH > 0}
		<svg
			{width}
			{height}
			role="img"
			aria-label="Scatter plot of {films.length} films: trailer {metric} against worldwide box office revenue, both on square-root scales."
		>
			<g transform="translate({margin.left},{margin.top})">
				<!-- Gridlines and tick labels -->
				<!-- Both x-axes are drawn; the inactive one fades out while switching. -->
				{#each xAxes as axis (axis.key)}
					<g opacity={axis.opacity} aria-hidden={axis.opacity < 0.5}>
						{#each ticks(axis.scale, axis.ticks) as t (t)}
							<line class="grid" x1={axis.scale(t)} x2={axis.scale(t)} y1={0} y2={innerH} />
							<text class="tick" x={axis.scale(t)} y={innerH + 18} text-anchor="middle">{short(t)}</text>
						{/each}
					</g>
				{/each}
				{#each ticks(y, Y_TICKS) as t (t)}
					<line class="grid" x1={0} x2={innerW} y1={y(t)} y2={y(t)} />
					<text class="tick" x={-10} y={y(t)} dy="0.32em" text-anchor="end">{fmtDollars(t)}</text>
				{/each}

				<!-- Axis titles -->
				<text class="axis-title" x={innerW / 2} y={innerH + 44} text-anchor="middle">
					{metric === 'views' ? 'Views' : 'Likes'} on the film's most-viewed YouTube trailer (square-root scale)
				</text>
				<text
					class="axis-title"
					transform="translate({-margin.left + 16},{innerH / 2}) rotate(-90)"
					text-anchor="middle"
				>
					Worldwide box office (square-root scale)
				</text>

				<!-- Dots. The labelled extremes are drawn last so they sit on top, in gold. -->
				{#each [...films].sort((a, b) => +extremes.has(a) - +extremes.has(b)) as d (d.title)}
					<circle
						class="dot"
						class:extreme={extremes.has(d)}
						class:hovered={hovered === d}
						cx={px(d)}
						cy={y(d.revenue)}
						r="4.5"
					/>
				{/each}

				<!-- Labels for the extremes -->
				{#each labelled as l (l.film.title)}
					{@const cx = px(l.film)}
					{@const cy = y(l.film.revenue)}
					{#if l.at}
						{@const lx = l.at[0] * innerW}
						{@const ly = y(l.at[1])}
						<line class="leader" x1={cx} y1={cy} x2={lx - 4} y2={ly - 4} />
						<text class="label" x={lx} y={ly} text-anchor={l.anchor}>{l.film.title}</text>
					{:else}
						<text class="label" x={cx + l.dx} y={cy + l.dy} text-anchor={l.anchor}>{l.film.title}</text>
					{/if}
				{/each}

				<!-- Invisible 24px hit areas, on top so hovering is easy -->
				{#each films as d (d.title)}
					<circle
						class="hit"
						cx={px(d)}
						cy={y(d.revenue)}
						r="12"
						role="button"
						tabindex="0"
						aria-label="{d.title} ({d.year}): {fmtFull(d.likes)} likes, {fmtFull(d.views)} views, {fmtDollarsFull(d.revenue)} worldwide"
						onpointerenter={() => (hovered = d)}
						onpointerleave={() => (hovered = null)}
						onfocus={() => (hovered = d)}
						onblur={() => (hovered = null)}
					/>
				{/each}
			</g>
		</svg>

		{#if hovered}
			{@const left = margin.left + px(hovered)}
			{@const top = margin.top + y(hovered.revenue)}
			<div
				class="tooltip"
				class:flip={left > width * 0.6}
				class:below={top < 90}
				style:left="{left}px"
				style:top="{top}px"
				aria-hidden="true"
			>
				<strong>{hovered.title}</strong> <span class="year">({hovered.year})</span>
				<dl>
					<dt>Trailer likes</dt>
					<dd>{fmtFull(hovered.likes)}</dd>
					<dt>Trailer views</dt>
					<dd>{fmtFull(hovered.views)}</dd>
					<dt>Box office</dt>
					<dd>{fmtDollarsFull(hovered.revenue)}</dd>
				</dl>
			</div>
		{/if}
	{/if}
</div>

<style>
	.chart {
		position: relative;
		width: 100%;
		height: 100%;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.grid {
		stroke: var(--grid);
		stroke-width: 1;
	}
	.tick {
		fill: var(--muted);
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
	}
	.axis-title {
		fill: var(--muted);
		font-size: 0.8rem;
	}
	.dot {
		fill: var(--dot);
		stroke: var(--bg);
		stroke-width: 2;
		transition: r 0.15s;
	}
	.dot.extreme {
		fill: var(--accent);
	}
	.dot.hovered {
		r: 7;
	}
	.label {
		fill: var(--accent);
		font-size: 0.75rem;
		paint-order: stroke;
		stroke: var(--bg);
		stroke-width: 4px;
		stroke-linejoin: round;
		pointer-events: none;
	}
	.leader {
		stroke: var(--accent);
		stroke-width: 1;
		pointer-events: none;
	}
	.hit {
		fill: transparent;
		cursor: pointer;
	}
	.hit:focus {
		outline: none;
	}
	.hit:focus-visible {
		stroke: var(--accent);
		stroke-width: 1.5;
	}

	.tooltip {
		position: absolute;
		z-index: 2;
		transform: translate(12px, calc(-100% - 12px));
		min-width: 11rem;
		padding: 0.6rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
		font-size: 0.8rem;
		line-height: 1.35;
		pointer-events: none;
		white-space: nowrap;
	}
	.tooltip.flip {
		transform: translate(calc(-100% - 12px), calc(-100% - 12px));
	}
	.tooltip.below {
		transform: translate(12px, 12px);
	}
	.tooltip.flip.below {
		transform: translate(calc(-100% - 12px), 12px);
	}
	.year {
		color: var(--muted);
	}
	dl {
		display: grid;
		grid-template-columns: auto auto;
		gap: 0.15rem 1rem;
		margin: 0.4rem 0 0;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>
