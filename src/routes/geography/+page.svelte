<script>
	import BackLink from '#lib/components/BackLink.svelte';
	import NetflixGenres from '#lib/components/NetflixGenres.svelte';
</script>

<svelte:head>
	<title>Geography · Movie Vis</title>
</svelte:head>

<BackLink />

<main>
	<NetflixGenres />
</main>

<style>
	main {
		max-width: 72rem;
		margin: 0 auto;
		padding: 5rem 1rem 50vh;
	}
</style>
