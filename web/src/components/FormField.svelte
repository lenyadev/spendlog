<script lang="ts">
  type Props = {
    label: string;
    name: string;
    type?: 'text' | 'email' | 'password';
    value?: string;
    error?: string;
    autocomplete?: 'email' | 'username' | 'current-password' | 'new-password' | 'off';
  };

  let {
    label,
    name,
    type = 'text',
    value = $bindable(''),
    error = '',
    autocomplete = 'off',
  }: Props = $props();
</script>

<fieldset class="fieldset">
  <label class="label" for={name}>{label}</label>
  <input
    id={name}
    {name}
    {type}
    {autocomplete}
    class="input w-full {error ? 'input-error' : ''}"
    bind:value
  />
  {#if error}
    <p class="text-error text-sm">{error}</p>
  {/if}
</fieldset>
