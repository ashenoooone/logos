<script setup lang="ts">
defineProps<{
  no: string
  log: string
  role: 'Администратор' | 'Менеджер'
  title: string
  story: string
  img: string
}>()
</script>

<template>
  <div class="story">
    <header class="story-top">
      <span class="kicker">История {{ no }} · {{ log }}</span>
      <span class="role" :class="role === 'Администратор' ? 'role-admin' : 'role-manager'">{{ role }}</span>
    </header>
    <h1 class="story-title">{{ title }}</h1>
    <p class="story-quote">{{ story }}</p>
    <div class="story-body">
      <div class="story-criteria"><slot /></div>
      <figure class="story-mockup" v-motion :initial="{ opacity: 0, y: 24 }" :enter="{ opacity: 1, y: 0, transition: { delay: 150 } }">
        <img :src="img" :alt="`Макет: ${title}`" />
        <figcaption>Макет из YouGile</figcaption>
      </figure>
    </div>
  </div>
</template>
