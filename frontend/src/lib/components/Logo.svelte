<script lang="ts">
	let { size = 24, class: className = '' }: { size?: number; class?: string } = $props();

	// „TD“ im Hintergrund, davor der Haken – gleiche Form wie static/favicon.svg
	const CHECK = 'M17 35l10 10 20-23';
</script>

<svg viewBox="0 0 64 64" width={size} height={size} class={className} aria-hidden="true">
	<rect width="64" height="64" rx="14" class="fill-accent" />
	<g class="fill-accent-fg" fill-opacity=".3" fill-rule="evenodd">
		<path d="M7 14h23v7h-8v29h-7V21H7z" />
		<path d="M32 14h7a18 18 0 0 1 0 36h-7zm7 7v22a11 11 0 0 0 0-22z" />
	</g>
	<path
		d={CHECK}
		fill="none"
		stroke-width="12"
		stroke-linecap="round"
		stroke-linejoin="round"
		class="stroke-accent"
	/>
	<path
		d={CHECK}
		fill="none"
		stroke-width="6.5"
		stroke-linecap="round"
		stroke-linejoin="round"
		class="stroke-accent-fg"
	/>
</svg>
