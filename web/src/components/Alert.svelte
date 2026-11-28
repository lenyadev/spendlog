<script lang="ts">
    type Props = {
        message: string;
        kind?: 'error' | 'success' | 'warning';
    };

    let { message, kind = 'error' }: Props = $props();

    const classes = {
        error: 'alert-error',
        success: 'alert-success',
        warning: 'alert-warning',
    };
</script>

{#if message}
    <div role="alert" class="alert alert-soft {classes[kind]}">
        <span>{message}</span>
    </div>
{/if}