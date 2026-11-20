<script>
	import BackLink from '#lib/components/BackLink.svelte';
</script>

<svelte:head>
	<title>Geography · Movie Vis</title>
</svelte:head>

<BackLink />

<main>
	<h1>Which movies are most popular in which areas of the world?</h1>
	<div class="vis-placeholder">Visualization coming soon</div>
</main>

<style>
	main {
		max-width: 64rem;
		margin: 0 auto;
		padding: 5rem 1rem 3rem;
	}
	h1 {
		font-size: clamp(1.5rem, 3vw, 2.2rem);
		margin: 0 0 2rem;
	}
	.vis-placeholder {
		display: grid;
		place-items: center;
		min-height: 60vh;
		color: var(--muted);
		border: 1px dashed var(--border);
		border-radius: 12px;
	}
</style>
