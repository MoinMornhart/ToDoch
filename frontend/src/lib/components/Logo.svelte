<script lang="ts">
	let { size = 24, class: className = '' }: { size?: number; class?: string } = $props();
</script>

<svg viewBox="0 0 64 64" width={size} height={size} class={className} aria-hidden="true">
	<rect width="64" height="64" rx="14" class="fill-accent" />
	<path
		d="M18 34l10 10 18-21"
		fill="none"
		stroke-width="6"
		stroke-linecap="round"
		stroke-linejoin="round"
		class="stroke-accent-fg"
	/>
</svg>
