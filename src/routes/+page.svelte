<script>
	const questions = [
		{
			href: '/geography',
			label: 'Part 1',
			text: 'Which movies are most popular in which areas of the world?'
		},
		{
			href: '/trailers-box-office',
			label: 'Part 2',
			text: 'Are movie trailer likes and views on YouTube correlated with its success at the Box Office?'
		}
	];
</script>

<svelte:head>
	<title>Movie Vis</title>
</svelte:head>

<main>
	<header>
		<p class="eyebrow">IMDb Top 250</p>
		<h1>Two questions about the movies we love</h1>
	</header>

	<nav>
		{#each questions as q (q.href)}
			<a class="card" href={q.href}>
				<span class="label">{q.label}</span>
				<span class="question">{q.text}</span>
				<span class="arrow" aria-hidden="true">→</span>
			</a>
		{/each}
	</nav>
</main>

<style>
	main {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 3rem;
		max-width: 64rem;
		margin: 0 auto;
		padding: 4rem 1rem;
		background: radial-gradient(ellipse at top, color-mix(in srgb, var(--gold) 14%, transparent), transparent 60%);
	}
	header {
		text-align: center;
	}
	.eyebrow {
		margin: 0 0 0.5rem;
		color: var(--accent);
		font-size: 0.8rem;
		font-weight: 600;
		letter-spacing: 0.2em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font-size: clamp(1.8rem, 4vw, 2.8rem);
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	nav {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
		gap: 1.5rem;
	}
	.card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: 14rem;
		padding: 2rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
	}
	.card:hover,
	.card:focus-visible {
		border-color: var(--accent);
		transform: translateY(-3px);
		box-shadow: 0 12px 32px rgb(0 0 0 / 0.5);
		outline: none;
	}
	.label {
		color: var(--muted);
		font-size: 0.8rem;
		letter-spacing: 0.15em;
		text-transform: uppercase;
	}
	.question {
		font-size: 1.35rem;
		font-weight: 600;
		line-height: 1.35;
	}
	.arrow {
		margin-top: auto;
		color: var(--accent);
		font-size: 1.5rem;
		transition: transform 0.2s;
	}
	.card:hover .arrow {
		transform: translateX(4px);
	}
</style>
