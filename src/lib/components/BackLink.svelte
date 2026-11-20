<a class="back" href="/" aria-label="Back to the landing page">
	<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
		<path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
	</svg>
</a>

<style>
	.back {
		position: fixed;
		top: 1rem;
		left: 1rem;
		z-index: 10;
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 50%;
		color: var(--text);
		background: rgb(20 20 24 / 0.75);
		border: 1px solid var(--border);
		backdrop-filter: blur(6px);
		transition: border-color 0.15s, color 0.15s;
	}
	.back:hover,
	.back:focus-visible {
		color: var(--accent);
		border-color: var(--accent);
	}
</style>
