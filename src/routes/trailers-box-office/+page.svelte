<script>
	import { onMount } from 'svelte';
	import * as d3 from 'd3';
	import BackLink from '#lib/components/BackLink.svelte';

	// Placeholder steps: replace the text, and handle each step in onStepEnter.
	const steps = [
		'Step 1: introduce the dataset.',
		'Step 2: trailer views vs. box office revenue.',
		'Step 3: trailer likes vs. box office revenue.',
		'Step 4: takeaway.'
	];

	let activeStep = $state(0);
	let graphic;

	function onStepEnter({ index }) {
		activeStep = index;
		// Swap this for real chart updates.
		d3.select(graphic).select('.step-readout').text(`Active step: ${index + 1}`);
	}

	onMount(() => {
		let scroller;
		let cancelled = false;

		// scrollama uses browser APIs, so load it only on the client.
		import('scrollama').then(({ default: scrollama }) => {
			if (cancelled) return;
			scroller = scrollama();
			scroller.setup({ step: '.step', offset: 0.5 }).onStepEnter(onStepEnter);
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

<svelte:head>
	<title>Trailers & Box Office · Movie Vis</title>
</svelte:head>

<BackLink />

<main>
	<header>
		<h1>Are movie trailer likes and views on YouTube correlated with its success at the Box Office?</h1>
	</header>

	<section class="scrolly">
		<div class="graphic" bind:this={graphic}>
			<p class="step-readout">Active step: 1</p>
		</div>

		<div class="steps">
			{#each steps as text, i (i)}
				<div class="step" class:active={activeStep === i}>
					<p>{text}</p>
				</div>
			{/each}
		</div>
	</section>
</main>

<style>
	main {
		max-width: 72rem;
		margin: 0 auto;
		padding: 5rem 1rem 50vh;
	}
	header h1 {
		font-size: clamp(1.5rem, 3vw, 2.2rem);
		margin: 0 0 20vh;
		max-width: 48rem;
	}
	.scrolly {
		position: relative;
		display: flex;
		gap: 2rem;
	}
	.graphic {
		position: sticky;
		top: 10vh;
		flex: 1 1 60%;
		height: 80vh;
		display: grid;
		place-items: center;
		color: var(--muted);
		border: 1px dashed var(--border);
		border-radius: 12px;
	}
	.steps {
		flex: 1 1 40%;
	}
	.step {
		margin: 0 0 80vh;
		padding: 1.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		opacity: 0.35;
		transition: opacity 0.3s, border-color 0.3s;
	}
	.step:last-child {
		margin-bottom: 0;
	}
	.step.active {
		opacity: 1;
		border-color: var(--accent);
	}
	.step p {
		margin: 0;
	}

	@media (max-width: 48rem) {
		.scrolly {
			flex-direction: column;
		}
		.graphic {
			top: 0;
			height: 60vh;
			z-index: 0;
		}
		.steps {
			position: relative;
			z-index: 1;
		}
	}
</style>
