<script lang="ts">
  import FormField from "$components/FormField.svelte";
  import Alert from "$components/Alert.svelte";

  let email = $state('');
  let password = $state('');
</script>

<div class="card bg-base-100 mx-auto max-w-sm shadow-sm">
  <div class="card-body gap-2">
    <h2 class="card-title">Вход</h2>
    <Alert message={password.length > 0 && password.length < 8 ? 'Пароль слишком короткий' : ''} />
    <FormField label="Email" name="email" type="email" autocomplete="email" bind:value={email} />
    <FormField
      label="Пароль"
      name="password"
      type="password"
      autocomplete="current-password"
      bind:value={password}
      error={password.length > 0 && password.length < 8 ? 'Минимум 8 символов' : ''}
    />
    <button class="btn btn-primary mt-2">Войти</button>
  </div>
</div>