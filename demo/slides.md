---
title: LOGOS · Sprint Review 01
info: Обзор первого спринта LOGOS — единого рабочего места для общения с клиентами.
colorSchema: light
transition: slide-left
fonts:
  sans: Inter
  weights: '400,500,600,700,800'
  provider: google
class: dark-slide
---

<div class="absolute inset-0 flex flex-col justify-between" style="padding: 2.4rem 3.2rem">

<div class="flex justify-between items-center">
  <span class="kicker">Презентация продукта · Спринт 01</span>
  <span class="pill" style="background: rgb(255 255 255 / 0.1); color: #fff">Sprint Review</span>
</div>

<div>
  <div class="flex items-start gap-3" v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0 }">
    <h1 style="font-size: 7rem; letter-spacing: -0.05em; font-weight: 800">LOGOS</h1>
    <span class="mt-5 w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold"
      style="background: var(--red)"
      v-motion :initial="{ scale: 0 }" :enter="{ scale: 1, transition: { delay: 600, type: 'spring', stiffness: 300 } }">8</span>
  </div>
  <p class="text-3xl font-semibold mt-4 leading-tight" v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { delay: 300 } }">
    Все сообщения.<br><span style="color: #9a9a9a">Одно рабочее место.</span>
  </p>
</div>

<div class="flex justify-between items-end">
  <p class="text-sm" style="color: #c4c4c4">Система коммуникации транспортной компании с клиентами</p>
  <div class="text-right">
    <div class="kicker">Команда проекта</div>
    <div class="text-sm mt-1" style="line-height: 1.6">Гонтарь · Дрыжов · Вертянкин<br>Смирников · Черномашенцев · Годунов</div>
  </div>
</div>

</div>

<!--
Добрый день. Мы — команда LOGOS. Покажем, что сделали за первый спринт.
Красная «8» у логотипа — это восемь историй первого спринта, о них и расскажем.
-->

---

<span class="kicker">Проблема</span>

# Клиенты пишут везде.<br>Менеджеры — не успевают.

<div class="grid grid-cols-[1fr_auto_1fr] gap-8 items-center mt-10">

<div class="relative h-64">
  <div class="card absolute left-0 top-0 w-64" v-click>
    <div class="flex justify-between text-xs"><b>Telegram</b><span style="color: var(--dim)">12:41</span></div>
    <p class="text-sm mt-1">Где мой заказ? Уже неделю жду</p>
  </div>
  <div class="card absolute left-20 top-22 w-64" v-click>
    <div class="flex justify-between text-xs"><b>WhatsApp</b><span style="color: var(--dim)">12:10</span></div>
    <p class="text-sm mt-1">Можно вернуть товар без чека?</p>
  </div>
  <div class="card absolute left-6 top-48 w-64" v-click>
    <div class="flex justify-between text-xs"><b>VK</b><span style="color: var(--red)">не прочитано</span></div>
    <p class="text-sm mt-1">Алло? Кто-нибудь ответит?</p>
  </div>
</div>

<div class="text-4xl" style="color: var(--dim)" v-click>→</div>

<div class="tile tile-night" v-click>
  <div class="kicker" style="color: #c4c4c4">LOGOS</div>
  <p class="text-2xl font-semibold mt-2 leading-snug">Все переписки —<br>в одном интерфейсе</p>
  <p class="text-sm mt-3" style="color: #dcdcdc">Менеджеры отвечают быстрее, обращения не теряются между каналами.</p>
</div>

</div>

<!--
Начнём с проблемы. Клиенты транспортной компании пишут в разные мессенджеры. [клик] Telegram, [клик] WhatsApp, [клик] VK.
Менеджер прыгает между приложениями, и часть сообщений просто теряется.
[клик] LOGOS собирает все переписки в одном окне. [клик] Цель простая — не терять клиентов из-за потерянных сообщений.
-->

---

<span class="kicker">Для кого</span>

# Заказчик — транспортная компания

<p class="lead mt-3">В системе две роли. Каждая история дальше — от лица одной из них.</p>

<div class="grid grid-cols-2 gap-6 mt-8">

<div class="tile tile-violet h-52 flex flex-col justify-between" v-motion :initial="{ opacity: 0, x: -40 }" :enter="{ opacity: 1, x: 0 }">
  <span class="kicker" style="color: rgb(255 255 255 / 0.8)">01 · Роль</span>
  <div>
    <div class="text-3xl font-bold">Администратор</div>
    <p class="mt-2 text-sm leading-relaxed">Приглашает менеджеров, подключает каналы и управляет стандартными тегами.</p>
  </div>
</div>

<div class="tile tile-green h-52 flex flex-col justify-between" v-motion :initial="{ opacity: 0, x: 40 }" :enter="{ opacity: 1, x: 0, transition: { delay: 200 } }">
  <span class="kicker" style="color: rgb(34 34 34 / 0.7)">02 · Роль</span>
  <div>
    <div class="text-3xl font-bold">Менеджер</div>
    <p class="mt-2 text-sm leading-relaxed">Принимает сообщения, общается с клиентами и организует диалоги.</p>
  </div>
</div>

</div>

<!--
Заказчик — транспортная компания. Одна установка — одна компания.
Ролей две: фиолетовая — администратор, зелёная — менеджер. Эти цвета будут на каждом слайде с историей, чтобы было видно, чья это история.
-->

---

<span class="kicker">План работ</span>

# Два спринта

<p class="lead mt-2">Сначала — единое рабочее место. Затем — удобная работа с клиентами и командой.</p>

<div class="grid grid-cols-2 gap-6 mt-6">

<div class="card" style="box-shadow: 0 0 0 2px var(--ink)">
  <div class="flex justify-between items-center mb-3">
    <b class="text-lg">01 · Первый спринт</b><span class="pill pill-dark">сегодня</span>
  </div>
  <ol class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm list-none p-0 m-0">
    <li>Регистрация менеджеров</li>
    <li>Управление мессенджерами</li>
    <li>Пароль для учётной записи</li>
    <li>Приём сообщений</li>
    <li>Вход в учётную запись</li>
    <li>Сортировка сообщений</li>
    <li>Изменение данных</li>
    <li>Теги</li>
  </ol>
</div>

<div class="card" v-click style="background: var(--bg-soft); box-shadow: none">
  <div class="flex justify-between items-center mb-3">
    <b class="text-lg" style="color: var(--dim)">02 · Второй спринт</b><span class="pill" style="background: #fff">далее</span>
  </div>
  <ol class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm list-none p-0 m-0" style="color: var(--dim)">
    <li>Шаблоны ответов</li>
    <li>Внутренние комментарии</li>
    <li>Закрепление диалогов</li>
    <li>Передача обращений</li>
    <li>История обращений</li>
    <li>Формирование отчёта</li>
    <li>Объединение контактов</li>
    <li>Мониторинг менеджеров</li>
    <li>Заметки о клиентах</li>
    <li>Журнал действий</li>
  </ol>
</div>

</div>

<!--
Работу разбили на два спринта. Первый — фундамент: доступ, каналы, входящие. Это сегодня.
[клик] Второй — то, что делает работу удобнее: шаблоны, комментарии, отчёты, мониторинг. К нему вернёмся в конце.
-->

---

<span class="kicker">Сценарий спринта 01</span>

# Путь от приглашения до ответа клиенту

<div class="grid grid-cols-4 gap-4 mt-10">
  <div v-for="(s, i) in [
      ['Админ', 'приглашает менеджера', '1.1'],
      ['Менеджер', 'задаёт пароль', '1.2'],
      ['Менеджер', 'входит в систему', '2.1'],
      ['Менеджер', 'меняет свои данные', '2.2'],
      ['Админ', 'подключает Telegram', '3.1'],
      ['Менеджер', 'получает и отвечает', '3.2'],
      ['Менеджер', 'сортирует и фильтрует', '4.1'],
      ['Менеджер', 'ставит теги', '4.2'],
    ]" :key="i"
    v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { delay: 120 * i } }"
    class="card relative">
    <div class="flex justify-between items-center">
      <span class="text-xs font-bold num" style="color: var(--dim)">{{ String(i + 1).padStart(2, '0') }}</span>
      <span class="w-2.5 h-2.5 rounded-full" :style="{ background: s[0] === 'Админ' ? 'var(--violet)' : 'var(--green)' }"></span>
    </div>
    <div class="text-xs mt-3" style="color: var(--dim)">{{ s[0] }}</div>
    <div class="text-sm font-semibold leading-snug">{{ s[1] }}</div>
    <div class="text-xs mt-2 num" style="color: var(--dim)">История {{ s[2] }}</div>
  </div>
</div>

<div class="flex gap-6 mt-8 text-sm" style="color: var(--dim)">
  <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background: var(--violet)"></span>Администратор</span>
  <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background: var(--green)"></span>Менеджер</span>
</div>

<!--
Все восемь историй складываются в один сценарий — так и будем рассказывать.
Админ приглашает менеджера, тот задаёт пароль и входит. Админ подключает Telegram — и менеджер начинает получать сообщения, отвечать, сортировать и размечать их тегами.
Три акта: доступ, каналы и сообщения, порядок во входящих.
-->

---
layout: center
class: act act-violet
transition: fade
---

<div class="w-full">
  <span class="kicker">Акт 01 · истории 1.1 – 2.2</span>
  <h1 class="mt-3" style="font-size: 4.5rem" v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0 }">Доступ в систему</h1>
  <p class="mt-4 text-xl" style="opacity: 0.85">Как менеджер попадает в LOGOS и остаётся в безопасности.</p>
</div>

<!--
Первый акт — доступ. Публичной регистрации нет: в систему попадают только по приглашению администратора.
-->

---

<Story no="1.1" log="LOG-33" role="Администратор" title="Регистрация менеджеров"
  story="Как администратор, я хочу регистрировать менеджеров, чтобы они получили доступ к системе."
  img="/mockups/1-1.png">

- **Успех:** форма в «Сотрудниках» → аккаунт и письмо-приглашение
- **Некорректный email** — форма не отправится, ошибка под полем
- **Email уже есть** — «Этот email уже есть в системе»
- **Опечатка:** исправил адрес → новое письмо, старая ссылка не работает
- **Приглашение использовано** — повторно войти по ссылке нельзя

</Story>

<!--
Администратор открывает «Сотрудники», вводит имя и email менеджера. Система создаёт аккаунт и отправляет приглашение.
Неверный email — форма не уйдёт.
Email уже занят — понятное сообщение.
Ошиблись в адресе — исправили, новое письмо уходит на правильный адрес, старая ссылка перестаёт работать.
Использованное приглашение второй раз не сработает.
-->

---

<Story no="1.2" log="LOG-23" role="Менеджер" title="Пароль для учётной записи"
  story="Как менеджер, я хочу указать пароль для своей учётной записи, чтобы обеспечить её безопасность."
  img="/mockups/1-2.png">

- **Успех:** ссылка из письма → новый пароль → сразу в системе
- **Пароль слабый или не совпадает** — подсказка, что именно исправить
- **Ссылка использована или истекла** — «обратитесь к администратору за новым приглашением»

</Story>

<!--
Менеджер открывает письмо, переходит по ссылке и задаёт пароль. После сохранения он сразу в системе.
Требования к паролю видны заранее, ошибки — конкретные.
Просроченная или использованная ссылка — подсказываем, к кому идти.
-->

---

<Story no="2.1" log="LOG-27" role="Менеджер" title="Вход в учётную запись"
  story="Как менеджер, я хочу входить в учётную запись, чтобы получить доступ к системе."
  img="/mockups/2-1.png">

- **Успех:** в шапке — профиль и кнопка «Выйти»
- **«Запомнить меня»** — до 30 дней, без него — до закрытия браузера
- **Неверные данные** — ошибка и сколько попыток осталось
- **5 ошибок подряд** — блокировка на 15 минут и ссылка на восстановление

</Story>

<!--
Вход по email и паролю. После входа в шапке видно, кто вошёл.
«Запомнить меня» держит сессию месяц, без галочки — до закрытия браузера.
При ошибке показываем, сколько попыток осталось.
После пяти ошибок — пауза 15 минут. Это защита от подбора пароля.
-->

---

<Story no="2.2" log="LOG-28" role="Менеджер" title="Изменение данных учётной записи"
  story="Как менеджер, я хочу изменить данные для входа, чтобы восстановить доступ к системе."
  img="/mockups/2-2.png">

- **Новый email** работает только после подтверждения по ссылке
- **Смена пароля** — с текущим; «Выйти на других устройствах» включено
- **Ошибка** — видно, какое условие нарушено
- **«Забыли пароль?»** — письмо со ссылкой на новый пароль
- **Ссылка** одноразовая и живёт 1 час
- **Письма нет** — подсказка про «Спам», повтор через 60 секунд

</Story>

<!--
В профиле менеджер меняет имя, email и пароль.
Новый email включается только после подтверждения — опечатка не заблокирует вход.
Пароль меняется только с текущим, остальные устройства по умолчанию разлогиниваются.
Если что-то не так — видно, что именно.
Забыли пароль — восстановление по почте.
Ссылка одноразовая, час.
И подсказка про спам, повторная отправка через минуту.
-->

---
layout: center
class: act act-night
transition: fade
---

<div class="w-full">
  <span class="kicker">Акт 02 · истории 3.1 – 3.2</span>
  <h1 class="mt-3" style="font-size: 4.5rem" v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0 }">Каналы и сообщения</h1>
  <p class="mt-4 text-xl" style="opacity: 0.85">Подключаем мессенджер — и сообщения клиентов приходят в одно окно.</p>
</div>

<!--
Второй акт — сердце продукта: каналы и входящие.
-->

---

<Story no="3.1" log="LOG-29" role="Администратор" title="Управление мессенджерами"
  story="Как администратор, я хочу управлять мессенджерами, чтобы менеджеры получали сообщения от клиентов."
  img="/mockups/3-1.png">

- **Успех:** токен доступа → канал создан, статус «подключён»
- **Неверный токен** — канал не добавляется, видна ошибка
- **Канал сломался** — статус ошибки и кнопка «Переподключить»
- **Отключение** — новых сообщений нет, история остаётся

</Story>

<!--
Администратор в разделе «Каналы» вставляет токен бота — канал подключён. Первый канал — Telegram Bot API.
Неверный токен проверяем сразу, канал не создаётся.
Если канал перестал работать — видно статус ошибки, можно переподключить.
При отключении история переписки не пропадает.
-->

---

<Story no="3.2" log="LOG-30" role="Менеджер" title="Приём сообщений от клиентов"
  story="Как менеджер, я хочу принимать сообщения клиентов, чтобы агрегировать сообщения из разных мессенджеров."
  img="/mockups/3-2.png">

- **Успех:** все диалоги одним списком, ответ с вложениями, статус «доставлено»
- **Новое сообщение** — звук, счётчик на вкладке, непрочитанные у диалога и всего
- **Ошибка отправки** — «Не доставлено» и кнопка повтора

</Story>

<!--
Это главный экран — «Входящие». Слева все диалоги из всех каналов, справа переписка. Можно читать вложения и отвечать с файлом.
Новое сообщение не пропустить: звук, счётчик во вкладке браузера, бейджи непрочитанных.
Если сообщение не ушло — менеджер это видит и может отправить ещё раз.
-->

---
layout: center
class: act act-orange
transition: fade
---

<div class="w-full">
  <span class="kicker">Акт 03 · истории 4.1 – 4.2</span>
  <h1 class="mt-3" style="font-size: 4.5rem" v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0 }">Порядок во входящих</h1>
  <p class="mt-4 text-xl" style="opacity: 0.85">Когда диалогов сотни, нужно быстро находить нужный.</p>
</div>

<!--
Третий акт — порядок. Когда диалогов много, нужна сортировка, фильтры и теги.
-->

---

<Story no="4.1" log="LOG-31" role="Менеджер" title="Сортировка сообщений"
  story="Как менеджер, я хочу сортировать сообщения клиентов, чтобы быстро находить нужные."
  img="/mockups/4-1.png">

- **По умолчанию** новые сверху, выбранная сортировка запоминается
- **Несколько фильтров** сразу, счётчик найденного, сброс по одному
- **Пусто** — пустое состояние и «Сбросить все фильтры»
- **Свои наборы фильтров** — сохранить и применить в один клик
- **Новые диалоги** не сдвигают список: «N новых — Показать»

</Story>

<!--
По умолчанию свежие диалоги сверху, но сортировку можно сменить — и она запомнится.
Фильтры комбинируются, видно, сколько нашлось.
Если ничего не нашлось — подсказываем, что сбросить.
Частые комбинации сохраняются под своим названием.
И важная деталь: список не прыгает под курсором. Новые диалоги ждут кнопки «Показать».
-->

---

<Story no="4.2" log="LOG-32" role="Менеджер" title="Классификация сообщений (теги)"
  story="Как менеджер, я хочу добавлять теги к диалогам клиентов, чтобы разделять их по тематикам."
  img="/mockups/4-2.png">

- **Успех:** тег виден в диалоге и в строке списка; свои теги видит только автор
- **Без учёта регистра:** «возврат» найдёт «Возврат», дубль не создать
- **Стандартные теги** меняет и удаляет только админ, при удалении тег снимается
- **Менеджер** удаляет только свои теги

</Story>

<!--
Менеджер вешает на диалог тег — выбирает существующий или создаёт новый.
Поиск не зависит от регистра, поэтому дублей «Возврат» и «возврат» не будет.
Общие теги — зона администратора.
Свои теги менеджер чистит сам.
-->

---

<span class="kicker">Итоги спринта 01</span>

# Собрали единое рабочее место

<div class="grid grid-cols-4 gap-4 mt-10">
  <div v-for="(t, i) in [
      ['8', 'историй реализовали', 'tile-violet'],
      ['34', 'приёмочных теста прошли', 'tile-night'],
      ['2', 'роли поддержали', 'tile-green'],
      ['1', 'канал подключили — Telegram', 'tile-orange'],
    ]" :key="i" :class="['tile h-40 flex flex-col justify-between', t[2]]"
    v-motion :initial="{ opacity: 0, scale: 0.9 }" :enter="{ opacity: 1, scale: 1, transition: { delay: 150 * i } }">
    <span class="num font-extrabold" style="font-size: 3.6rem; line-height: 1; letter-spacing: -0.04em">{{ t[0] }}</span>
    <span class="text-sm font-medium">{{ t[1] }}</span>
  </div>
</div>

<div class="flex gap-3 mt-8 flex-wrap" v-click>
  <span class="pill">Пригласили менеджеров</span>
  <span class="pill">Сделали вход и восстановление</span>
  <span class="pill">Собрали профиль</span>
  <span class="pill">Подключили каналы</span>
  <span class="pill">Объединили входящие</span>
  <span class="pill">Добавили фильтры</span>
  <span class="pill">Ввели теги</span>
</div>

<!--
Итог: реализовали восемь историй, прошли все тридцать четыре приёмочных теста, поддержали две роли и подключили первый канал — Telegram.
[клик] От приглашения сотрудника до ответа клиенту с тегом — весь путь закрыт.
-->

---

<span class="kicker">Что дальше</span>

# В спринте 02 сделаем работу<br>с клиентами и командой удобнее

<div class="grid grid-cols-5 gap-3 mt-8">
  <div v-for="(s, i) in [
      'Добавим шаблоны ответов', 'Закрепим диалоги', 'Покажем историю обращений', 'Объединим контакты', 'Добавим заметки о клиентах',
      'Добавим внутренние комментарии', 'Настроим передачу обращений', 'Сформируем отчёт', 'Запустим мониторинг менеджеров', 'Заведём журнал действий',
    ]" :key="i" class="card" style="padding: 0.9rem 1rem"
    v-motion :initial="{ opacity: 0, y: 16 }" :enter="{ opacity: 1, y: 0, transition: { delay: 80 * i } }">
    <div class="text-xs font-bold num" style="color: var(--dim)">{{ String(i + 1).padStart(2, '0') }}</div>
    <div class="text-sm font-semibold mt-2 leading-snug">{{ s }}</div>
  </div>
</div>

<!--
Во втором спринте — десять историй: шаблоны ответов, заметки и комментарии, передача обращений между менеджерами, формирование отчёта и мониторинг.
-->

---
layout: center
class: dark-slide
transition: fade
---

<div class="w-full">
  <span class="kicker">LOGOS · Спринт 01</span>
  <h1 class="mt-4" style="font-size: 5.5rem" v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0 }">Спасибо!</h1>
  <p class="text-3xl font-semibold mt-2" style="color: #9a9a9a" v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { delay: 400 } }">Вопросы?</p>
  <p class="mt-14 text-sm" style="color: #c4c4c4">LOGOS — единое рабочее место для общения с клиентами</p>
</div>

<!--
Спасибо! Готовы ответить на вопросы.
-->
