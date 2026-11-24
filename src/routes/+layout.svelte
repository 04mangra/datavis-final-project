<script>
	import favicon from '#lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}

<style>
	:global(:root) {
		/* Palette: Coolors "Black & Gold" (000000-14213d-fca311-e5e5e5-ffffff) */
		--black: #000000;
		--prussian: #14213d;
		--gold: #fca311;
		--alabaster: #e5e5e5;
		--white: #ffffff;
		/* Not in the palette: a lighter Prussian blue. #14213d is only 1.31:1 on black,
		   too faint for lines; this is 2.2:1. */
		--prussian-light: #2c4372;

		/* Roles (use these in components) */
		--bg: var(--black);
		--surface: var(--prussian);
		--border: var(--prussian-light);
		--grid: var(--prussian-light); /* chart gridlines */
		--text: var(--white);
		--muted: var(--alabaster); /* secondary text, axis ticks and titles */
		--accent: var(--gold); /* highlights: hover, active step, progress, chart extremes */
		--dot: var(--alabaster); /* ordinary chart dots */
		color-scheme: dark;
	}
	:global(*, *::before, *::after) {
		box-sizing: border-box;
	}
	:global(body) {
		margin: 0;
		background: var(--bg);
		color: var(--text);
		font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
		line-height: 1.5;
		-webkit-font-smoothing: antialiased;
	}
	:global(a) {
		color: inherit;
		text-decoration: none;
	}
</style>
