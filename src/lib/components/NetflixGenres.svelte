<script>
	import { onMount } from 'svelte';
	import WorldMap from '#lib/components/WorldMap.svelte';

	const steps = [
		'Exposition: Netflix is in more than 90 countries, each with its own weekly Top 10. It seems like everyone watches the same things.',
		'Rising action: Most Top 10 films are only popular in one country, and very few go global.',
		'Climax: Countries in the same part of the world like similar genres.',
		'Falling action: Some countries share taste with places far away, because of cultural ties, catalogue differences and local film industries.',
		'Resolution: Netflix is global, but taste is still local. Find your country.'
	];

	let activeStep = $state(0);

	onMount(() => {
		let scroller;
		let cancelled = false;

		// Own class name (not `.step`) so this scroller and the trailers
		// section's scroller never pick up each other's steps.
		import('scrollama').then(({ default: scrollama }) => {
			if (cancelled) return;
			scroller = scrollama();
			scroller
				.setup({ step: '.netflix-step', offset: 0.5 })
				.onStepEnter(({ index }) => {
					activeStep = index;
				});
		});

		const onResize = () => scroller?.resize();
		window.addEventListener('resize', onResize);
		return () => {
			cancelled = true;
			window.removeEventListener('resize', onResize);
			scroller?.destroy();
		};
	});
</script>

<header>
	<h1>Does location shape which movie genres countries watch on Netflix?</h1>
</header>

<section class="netflix-scrolly">
	<div class="netflix-graphic">
		<WorldMap {activeStep} />
	</div>

	<div class="netflix-steps">
		{#each steps as text, i (i)}
			<div class="netflix-step" class:active={activeStep === i}>
				<p>{text}</p>
			</div>
		{/each}
	</div>
</section>

<style>
	header h1 {
		font-size: clamp(1.5rem, 3vw, 2.2rem);
		margin: 0 0 20vh;
		max-width: 48rem;
	}
	.netflix-scrolly {
		position: relative;
		display: flex;
		gap: 2rem;
	}
	.netflix-graphic {
		position: sticky;
		top: 10vh;
		flex: 1 1 60%;
		height: 80vh;
		display: grid;
		place-items: center;
		padding: 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
	}
	.netflix-steps {
		flex: 1 1 40%;
	}
	.netflix-step {
		margin: 0 0 80vh;
		padding: 1.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		opacity: 0.35;
		transition: opacity 0.3s, border-color 0.3s;
	}
	.netflix-step:last-child {
		margin-bottom: 0;
	}
	.netflix-step.active {
		opacity: 1;
		border-color: var(--accent);
	}
	.netflix-step p {
		margin: 0;
	}

	@media (max-width: 48rem) {
		.netflix-scrolly {
			flex-direction: column;
		}
		.netflix-graphic {
			top: 0;
			height: 60vh;
			z-index: 0;
			background: var(--bg);
		}
		.netflix-steps {
			position: relative;
			z-index: 1;
		}
	}
</style>
