<script>
	import { onMount } from 'svelte';
	import * as d3 from 'd3';
	import BackLink from '#lib/components/BackLink.svelte';
	import LikesRevenueScatter from '#lib/components/LikesRevenueScatter.svelte';	

	/** @type {{ title: string, year: number, likes: number, views: number, revenue: number }[]} */

	let films = $state([]);

	// What the chart's x-axis shows, set by the Likes/Views toggle next to the chart.
	// Step text can read it too, e.g. {metric === 'views' ? '…' : '…'}.
	/** @type {'likes' | 'views'} */
	let metric = $state('likes');

	// Each step is a list of paragraphs. Steps 2–4 are still placeholders.
	const steps = $derived([
		[
		`<strong>Are movie trailer ${metric} on YouTube correlated with box office success?</strong>`,
		`Each dot is one film from the IMDb top 250, released 2008 to 2025. We took the ${metric} on its most-viewed YouTube trailer (as of Nov 2026) and its worldwide box office. Of the 250 films, <strong>184</strong> have public trailer likes, <strong>59</strong> of those came out in 2008 or later, and <strong>57</strong> are plotted here.`,
		`At first glance, <span style="color: var(--accent)">films with more trailer ${metric} tend to earn more</span>.`,
		`<strong>But does this hold up?</strong>`
		],
		['Step 2: placeholder.'],
		['Step 3: placeholder.'],
		['Step 4: placeholder.']
	]);

	const metrics = /** @type {const} */ ([
		['likes', 'Likes'],
		['views', 'Views']
	]);

	let activeStep = $state(0);
	let section;

	// The bar fills dot by dot, so it moves in step with the cards.
	let progress = $derived(steps.length > 1 ? activeStep / (steps.length - 1) : 1);

	// The section is taller than the screen and its stage is sticky. While the stage
	// is pinned, the vertical scroll distance is split into one equal zone per step.
	function scrollRange() {
		const top = section.getBoundingClientRect().top + window.scrollY;
		return { top, range: section.offsetHeight - window.innerHeight };
	}

	function update() {
		if (!section) return;
		const { top, range } = scrollRange();
		const p = range > 0 ? (window.scrollY - top) / range : 0;
		activeStep = Math.min(steps.length - 1, Math.max(0, Math.floor(p * steps.length)));
	}

	// Scroll to the middle of the step's zone.
	function goToStep(i) {
		const { top, range } = scrollRange();
		window.scrollTo({ top: top + ((i + 0.5) / steps.length) * range, behavior: 'smooth' });
	}

	// Clicking anywhere on the bar jumps to the nearest step.
	function onBarClick(event) {
		const rect = event.currentTarget.getBoundingClientRect();
		const fraction = (event.clientX - rect.left) / rect.width;
		goToStep(Math.round(fraction * (steps.length - 1)));
	}

	onMount(() => {
		// Klaus has no revenue and Hamilton isn't in this file, which leaves 57 films.
		d3.csv('/analysis_subset.csv', d3.autoType).then((rows) => {
			films = rows
				.filter((r) => r.revenue != null && r.most_viewed_likes != null && r.most_viewed_views != null)
				.map((r) => ({
					title: r.title,
					year: r.year,
					likes: r.most_viewed_likes,
					views: r.most_viewed_views,
					revenue: r.revenue
				}));
		});

		let frame = 0;
		const onScroll = () => {
			cancelAnimationFrame(frame);
			frame = requestAnimationFrame(update);
		};
		update();
		window.addEventListener('scroll', onScroll, { passive: true });
		window.addEventListener('resize', onScroll);
		return () => {
			cancelAnimationFrame(frame);
			window.removeEventListener('scroll', onScroll);
			window.removeEventListener('resize', onScroll);
		};
	});
</script>

<svelte:head>
	<title>Trailers & Box Office · Movie Vis</title>
</svelte:head>

<BackLink />

<main>
	<!-- One screen of scroll per step, plus the screen the stage itself fills. -->
	<section class="scrolly" bind:this={section} style:height="{(steps.length + 1) * 100}vh">
		<div class="stage">
			<header>
				<h1>Are movie trailer likes and views on YouTube correlated with its success at the Box Office?</h1>
			</header>

			<div class="graphic">
				<div class="chart-area">
					{#if films.length}
						<LikesRevenueScatter {films} {metric} />
					{/if}
				</div>

				<!-- Switches the chart's x-axis between trailer likes and trailer views. -->
				<div class="metric-toggle" role="group" aria-label="Chart x-axis">
					{#each metrics as [value, label] (value)}
						<button aria-pressed={metric === value} onclick={() => (metric = value)}>{label}</button>
					{/each}
				</div>
			</div>

			<nav class="progress" aria-label="Story progress">
				<!-- Mouse-only shortcut; keyboard and screen-reader users use the step buttons. -->
				<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
				<div class="track" onclick={onBarClick}>
					<div class="line"><div class="fill" style:width="{progress * 100}%"></div></div>
				</div>
				<ol>
					{#each steps as _, i (i)}
						<li style:left="{steps.length > 1 ? (i / (steps.length - 1)) * 100 : 50}%">
							<button
								class="dot"
								class:active={activeStep === i}
								class:done={i < activeStep}
								aria-label="Go to step {i + 1}"
								aria-current={activeStep === i ? 'step' : undefined}
								onclick={() => goToStep(i)}
							>
								<span class="num" aria-hidden="true">{i + 1}</span>
							</button>
						</li>
					{/each}
				</ol>
			</nav>

			<div class="strip">
				<div class="cards" style:--i={activeStep}>
					{#each steps as paragraphs, i (i)}
						<div class="step" class:active={activeStep === i} aria-hidden={activeStep !== i}>
							{#each paragraphs as text, j (j)}
								<p>{@html text}</p>
							{/each}
						</div>
					{/each}
				</div>
			</div>
		</div>
	</section>
</main>

<style>
	main {
		max-width: 48rem;
		margin: 0 auto;
		padding: 0 1rem;
	}

	/* The stage pins for the whole section and holds everything, so it all fits on one
	   screen: title, chart (takes the leftover height), progress bar, text strip. */
	.stage {
		position: sticky;
		top: 0;
		height: 100vh;
		height: 100dvh; /* the visible height, excluding mobile browser bars */
		display: grid;
		grid-template-rows: auto 1fr auto auto;
		/* minmax(0, …) stops the wide row of cards from stretching the page sideways. */
		grid-template-columns: minmax(0, 1fr);
		gap: 1rem;
		padding: 1rem 0 1.5rem;
	}
	header h1 {
		margin: 0;
		/* Keep clear of the fixed back button on narrow screens. */
		padding-inline: 3rem;
		font-size: clamp(1.1rem, 2.4vw, 1.8rem);
		line-height: 1.25;
		text-align: center;
	}
	/* Chart on the left, Likes/Views toggle in a narrow column on its right. */
	.graphic {
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.75rem;
	}
	.chart-area {
		height: 100%;
		min-width: 0;
	}
	.metric-toggle {
		display: flex;
		flex-direction: column;
		padding: 3px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface);
	}
	.metric-toggle button {
		padding: 0.45rem 0.8rem;
		border: 0;
		border-radius: 7px;
		background: none;
		color: var(--muted);
		font: inherit;
		font-size: 0.85rem;
		cursor: pointer;
		transition: background 0.2s, color 0.2s;
	}
	.metric-toggle button:hover {
		color: var(--text);
	}
	.metric-toggle button[aria-pressed='true'] {
		background: var(--accent);
		color: var(--bg);
		font-weight: 600;
	}
	.metric-toggle button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	/* Horizontal text strip. Each card is as wide as the chart (the full stage width);
	   the row slides one card per step, so neighbouring cards stay off-screen. */
	.strip {
		container-type: inline-size;
		overflow: hidden;
	}
	.cards {
		--card-w: 100cqi;
		--gap: 1.5rem;
		display: flex;
		gap: var(--gap);
		transform: translateX(calc(var(--i) * -1 * (var(--card-w) + var(--gap))));
		transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.step {
		flex: 0 0 var(--card-w);
		padding: 1.5rem;
		color: var(--muted);
		opacity: 0.35;
		transition: opacity 0.3s;
	}
	.step.active {
		opacity: 1;
		border-color: var(--accent);
	}
	.step p {
		margin: 0;
		font-size: 0.95rem;
	}
	.step p + p {
		margin-top: 0.6rem;
	}

	/* Horizontal progress bar with clickable dots. */
	.progress {
		position: relative;
		height: 28px;
		margin: 0 auto;
		width: min(20rem, 70%);
	}
	/* Tall invisible click area around the thin visible line. */
	.track {
		position: absolute;
		top: 50%;
		width: 100%;
		height: 28px;
		transform: translateY(-50%);
		display: flex;
		align-items: center;
		cursor: pointer;
	}
	.line {
		width: 100%;
		height: 2px;
		background: var(--border);
		border-radius: 1px;
	}
	.fill {
		height: 100%;
		background: var(--accent);
		border-radius: 1px;
		transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.progress ol {
		position: relative;
		height: 100%;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.progress li {
		position: absolute;
		top: 50%;
		transform: translate(-50%, -50%);
	}
	/* 28px button for an easy click target; the visible dot is drawn by ::before. */
	.dot {
		position: relative;
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}
	.dot::before {
		content: '';
		width: 12px;
		height: 12px;
		border-radius: 50%;
		border: 2px solid var(--muted);
		background: var(--bg);
		transition: background 0.2s, border-color 0.2s, transform 0.2s;
	}
	.dot.done::before {
		border-color: var(--accent);
		background: var(--accent);
	}
	.dot.active::before,
	.dot:hover::before,
	.dot:focus-visible::before {
		border-color: var(--accent);
		transform: scale(1.35);
	}
	.dot:focus-visible {
		outline: none;
	}
	/* Step number appears above the dot on hover, focus, or when active. */
	.num {
		position: absolute;
		bottom: 100%;
		color: var(--muted);
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
		opacity: 0;
		transition: opacity 0.2s;
	}
	.dot:hover .num,
	.dot:focus-visible .num,
	.dot.active .num {
		opacity: 1;
	}
	.dot.active .num {
		color: var(--accent);
	}

	@media (prefers-reduced-motion: reduce) {
		.cards,
		.fill {
			transition: none;
		}
	}
</style>
