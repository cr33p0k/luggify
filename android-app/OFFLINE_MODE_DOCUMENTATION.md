# Офлайн режим Luggify

## Общий принцип

Приложение использует стратегию **"сначала локально, потом сервер"** (offline-first). Все данные сохраняются на устройстве и синхронизируются с сервером при наличии интернета.

---

## Хранение данных

### Что сохраняется локально
- Список чеклистов пользователя
- Содержимое каждого чеклиста (город, даты, вещи)
- Состояние чеклиста (отмеченные, удалённые, добавленные вещи)
- **Прогноз погоды** (сохраняется при загрузке)

### Технология
- **DataStore** (Android Jetpack) для хранения данных в формате JSON
- Данные сохраняются в файле `checklists.preferences_pb`

---

## Онлайн режим

### Создание чеклиста
1. Пользователь выбирает город и даты
2. Запрос на сервер → генерация списка вещей + прогноз погоды
3. Чеклист сохраняется локально (с погодой)
4. Отображается пользователю

### Сохранение в "Мои чеклисты"
1. Пользователь нажимает "Сохранить"
2. Чеклист отправляется на сервер (привязывается к user_id)
3. Сервер возвращает чеклист с новым slug
4. Старая локальная версия удаляется, новая сохраняется

### Открытие чеклиста
1. Загружается локальная версия (мгновенно)
2. Если есть сеть → обновляется с сервера
3. Если погоды нет → загружается с сервера и сохраняется локально

### Редактирование чеклиста
1. Изменения сохраняются локально сразу (мгновенный отклик)
2. Отправляются на сервер в фоне
3. Если сервер недоступен → изменения остаются локально

### Удаление чеклиста
1. Удаляется локально сразу
2. Запрос на удаление отправляется на сервер

---

## Оффлайн режим

### Определение
Оффлайн режим активируется когда:
- Нет подключения к интернету
- Сервер недоступен (таймаут, ошибка сети)

### Что доступно
✅ Просмотр сохранённых чеклистов  
✅ Просмотр сохранённой погоды  
✅ Редактирование чеклистов (отметки, добавление, удаление вещей)  
✅ Удаление чеклистов  

### Что недоступно
❌ Создание новых чеклистов (требует сервер)  
❌ Поиск городов (требует сервер)  
❌ Обновление погоды (требует сервер)  

### Индикация
- В "Мои чеклисты" показывается баннер "Нет подключения к интернету"
- Изменения сохраняются локально без ошибок

---

## Синхронизация

### При загрузке "Мои чеклисты"
```
1. Показать локальные чеклисты (мгновенно)
2. Проверить сеть
3. Если есть сеть:
   - Загрузить список с сервера
   - Сохранить локальную погоду (не перезаписывать)
   - Обновить локальное хранилище
4. Если нет сети:
   - Показать баннер "Оффлайн"
   - Использовать локальные данные
```

### При открытии чеклиста
```
1. Показать локальную версию (с погодой если есть)
2. Если есть сеть и нет погоды:
   - Загрузить погоду с сервера
   - Сохранить локально
   - Обновить UI
```

### При сохранении изменений
```
1. Сохранить локально (мгновенно)
2. Отправить на сервер
3. Если успех → needsSync = false
4. Если ошибка → needsSync = true (синхронизируется позже)
```

### Автоматическая синхронизация
```
При открытии чеклиста:
1. Проверить needsSync
2. Если true + есть интернет → отправить на сервер
3. При успехе → needsSync = false
```

---

## Работа с погодой

### Загрузка погоды
- Погода загружается при создании нового чеклиста
- Погода загружается при открытии чеклиста (если её нет и есть сеть)

### Сохранение погоды
- Погода сохраняется локально вместе с чеклистом
- При синхронизации с сервером локальная погода сохраняется

### Обновление погоды
- **Всегда обновляется** при открытии чеклиста (если есть сеть)
- Даже если есть кэшированная погода — загружается актуальная
- Новая погода перезаписывает старую в кэше

---

## Предотвращение дубликатов

### Проблема
При обновлении погоды вызывается API генерации чеклиста, который возвращает новый чеклист с новым slug. Если его сохранить — появится дубликат.

### Решение
Параметр `saveLocally = false` при загрузке только погоды:
```kotlin
repository.generatePackingList(request, saveLocally = false)
```
Это загружает данные с сервера, но НЕ сохраняет новый чеклист. Погода сохраняется отдельно через `saveWeatherLocally()`.

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         UI (Compose)                         │
├─────────────────────────────────────────────────────────────┤
│                      LuggifyViewModel                        │
│  - Управляет состоянием UI                                  │
│  - Вызывает методы репозитория                              │
│  - Обрабатывает результаты                                  │
├─────────────────────────────────────────────────────────────┤
│                     LuggifyRepository                        │
│  - Решает: сервер или локальное хранилище                   │
│  - Синхронизирует данные                                    │
│  - Обрабатывает ошибки сети                                 │
├─────────────────────────────────────────────────────────────┤
│          LuggifyApi          │     ChecklistDataStore       │
│     (Retrofit + сервер)      │   (DataStore + локально)     │
└─────────────────────────────────────────────────────────────┘
```

---

## Файлы и их ответственность

### Модели данных
| Файл | Описание |
|------|----------|
| `data/models/Checklist.kt` | Модель чеклиста (город, даты, вещи, погода) |
| `data/models/City.kt` | Модель города |
| `data/models/DailyForecast.kt` | Модель прогноза погоды на день |

### Локальное хранилище
| Файл | Описание |
|------|----------|
| `data/datastore/ChecklistDataStore.kt` | Сохранение/загрузка чеклистов локально (DataStore) |
| `data/datastore/UserPreferencesDataStore.kt` | Сохранение настроек пользователя (город, даты, вещи по умолчанию) |

### Работа с сервером
| Файл | Описание |
|------|----------|
| `data/api/LuggifyApi.kt` | Интерфейс API (Retrofit) |
| `data/api/ApiClient.kt` | Настройка HTTP-клиента |

### Бизнес-логика
| Файл | Описание |
|------|----------|
| `data/repository/LuggifyRepository.kt` | **Главный файл синхронизации** — решает откуда брать данные (сервер/локально), обрабатывает ошибки сети, сохраняет данные |

### UI и состояние
| Файл | Описание |
|------|----------|
| `ui/viewmodel/LuggifyViewModel.kt` | Управление состоянием UI, вызов репозитория, загрузка погоды |
| `ui/screens/MyChecklistsScreen.kt` | Экран "Мои чеклисты" (показ оффлайн-баннера) |
| `ui/screens/ChecklistScreen.kt` | Экран чеклиста (автозагрузка погоды) |

### Утилиты
| Файл | Описание |
|------|----------|
| `utils/NetworkUtils.kt` | Проверка наличия интернета |

---

## Ключевые методы

### ChecklistDataStore.kt
```kotlin
getAllChecklists()      // Получить все локальные чеклисты
getChecklist(slug)      // Получить чеклист по slug
saveChecklist(...)      // Сохранить чеклист
saveAllChecklists(...)  // Перезаписать все чеклисты
deleteChecklist(slug)   // Удалить чеклист
updateChecklistState()  // Обновить состояние (отметки, вещи)
```

### LuggifyRepository.kt
```kotlin
generatePackingList(request, saveLocally)  // Генерация чеклиста
getChecklist(slug)                         // Загрузка с сервера/локально
getMyChecklists(userId)                    // Список чеклистов
saveChecklist(...)                         // Сохранение на сервер
updateChecklistState(...)                  // Обновление состояния
deleteChecklist(slug)                      // Удаление
saveWeatherLocally(slug, forecast)         // Сохранение погоды локально
getLocalChecklists()                       // Только локальные данные
```

### LuggifyViewModel.kt
```kotlin
loadMyChecklists()           // Загрузка списка чеклистов
openChecklistFromMyList()    // Открытие чеклиста из списка
loadChecklist(slug)          // Загрузка чеклиста
tryLoadWeather()             // Попытка загрузить погоду
refreshWeatherForecast()     // Загрузка погоды с сервера
saveChecklistState()         // Сохранение изменений
saveCurrentChecklist()       // Сохранение в "Мои чеклисты"
```

### NetworkUtils.kt
```kotlin
isNetworkAvailable(context)  // Проверка интернета
```

---

## Подробное объяснение кода

### 1. Локальное хранилище (ChecklistDataStore.kt)

Все чеклисты хранятся в одном JSON-файле через Android DataStore:

```kotlin
// Ключ для хранения
private val CHECKLISTS_KEY = stringPreferencesKey("all_checklists")

// Сохранение одного чеклиста
suspend fun saveChecklist(checklist: Checklist) {
    val currentChecklists = getAllChecklists().toMutableList()
    
    // Ищем существующий чеклист по slug
    val existingIndex = currentChecklists.indexOfFirst { it.slug == checklist.slug }
    
    if (existingIndex != -1) {
        // Если нашли — обновляем
        currentChecklists[existingIndex] = checklist
    } else {
        // Если не нашли — добавляем в начало списка
        currentChecklists.add(0, checklist)
    }
    
    // Сохраняем весь список как JSON строку
    context.checklistDataStore.edit { preferences ->
        preferences[CHECKLISTS_KEY] = gson.toJson(currentChecklists)
    }
}

// Получение всех чеклистов
suspend fun getAllChecklists(): List<Checklist> {
    val preferences = context.checklistDataStore.data.first()
    val json = preferences[CHECKLISTS_KEY] ?: return emptyList()
    return gson.fromJson(json, listType)  // JSON → List<Checklist>
}
```

**Суть:** Все чеклисты хранятся как один JSON-массив. При изменении одного чеклиста — перезаписывается весь массив.

---

### 2. Синхронизация списка чеклистов (LuggifyRepository.kt)

При загрузке "Мои чеклисты" происходит умное слияние данных:

```kotlin
suspend fun getMyChecklists(userId: String): Result<List<Checklist>> {
    // 1. Сначала получаем локальные данные
    val localChecklists = localStore.getAllChecklists()
    
    // 2. Пытаемся загрузить с сервера
    val result = api.getMyChecklists(userId)
    
    return result.fold(
        onSuccess = { serverChecklists ->
            // 3. Создаём карту локальных чеклистов для быстрого поиска
            val localMap = localChecklists.associateBy { it.slug }
            
            // 4. Для каждого серверного чеклиста сохраняем локальную погоду
            val mergedChecklists = serverChecklists.map { serverChecklist ->
                val localForecast = localMap[serverChecklist.slug]?.daily_forecast
                if (localForecast != null) {
                    // Есть локальная погода — сохраняем её
                    serverChecklist.copy(daily_forecast = localForecast)
                } else {
                    serverChecklist
                }
            }
            
            // 5. Сохраняем объединённый результат локально
            localStore.saveAllChecklists(mergedChecklists)
            
            Result.success(mergedChecklists)
        },
        onFailure = { error ->
            // Нет сети — возвращаем локальные данные
            if (localChecklists.isNotEmpty()) {
                Result.success(localChecklists)
            } else {
                Result.failure(error)
            }
        }
    )
}
```

**Суть:** Сервер не хранит погоду (она генерируется динамически). Поэтому при синхронизации мы сохраняем погоду из локального хранилища.

---

### 3. Обновление состояния чеклиста (LuggifyRepository.kt)

Когда пользователь отмечает вещь или добавляет новую:

```kotlin
suspend fun updateChecklistState(slug: String, state: ChecklistStateUpdate): Result<Checklist> {
    // 1. СНАЧАЛА сохраняем локально (мгновенный отклик UI)
    val localChecklist = localStore.updateChecklistState(
        slug = slug,
        checkedItems = state.checked_items,
        removedItems = state.removed_items,
        addedItems = state.added_items,
        items = state.items
    )
    
    if (localChecklist == null) {
        return Result.failure(Exception("Чеклист не найден"))
    }
    
    // 2. ПОТОМ пытаемся отправить на сервер (в фоне)
    val result = api.updateChecklistState(slug, state)
    
    return result.fold(
        onSuccess = { serverChecklist ->
            // Сервер ответил — сохраняем его версию, но с локальной погодой
            val merged = serverChecklist.copy(daily_forecast = localChecklist.daily_forecast)
            localStore.saveChecklist(merged)
            Result.success(merged)
        },
        onFailure = { 
            // Нет сети — возвращаем локальную версию (она уже сохранена)
            Result.success(localChecklist)
        }
    )
}
```

**Суть:** Сначала локально → потом сервер. Если сервер недоступен — не страшно, данные уже сохранены локально.

---

### 4. Загрузка погоды (LuggifyViewModel.kt)

При открытии чеклиста проверяем, нужно ли загрузить погоду:

```kotlin
// Вызывается при входе на экран чеклиста
fun tryLoadWeather() {
    val checklist = _uiState.value.checklist ?: return
    
    // Всегда загружаем актуальную погоду (если есть сеть)
    // Даже если есть кэшированная — обновляем
    refreshWeatherForecast(checklist.city, checklist.start_date, checklist.end_date)
}

private fun refreshWeatherForecast(city: String, startDate: String, endDate: String) {
    // Проверяем сеть
    if (!NetworkUtils.isNetworkAvailable(appContext)) return
    
    val request = PackingRequest(city = city, start_date = startDate, end_date = endDate)
    
    viewModelScope.launch {
        // saveLocally = false — НЕ создаём новый чеклист, только получаем данные
        repository.generatePackingList(request, saveLocally = false).fold(
            onSuccess = { checklistWithForecast ->
                val currentChecklist = _uiState.value.checklist ?: return@fold
                val forecast = checklistWithForecast.daily_forecast ?: return@fold
                
                // 1. Обновляем UI
                _uiState.value = _uiState.value.copy(
                    checklist = currentChecklist.copy(daily_forecast = forecast)
                )
                
                // 2. Сохраняем погоду локально для оффлайн доступа
                repository.saveWeatherLocally(currentChecklist.slug, forecast)
            },
            onFailure = { /* игнорируем ошибку */ }
        )
    }
}
```

**Суть:** `saveLocally = false` — ключевой параметр! Он говорит "дай мне данные, но не сохраняй новый чеклист". Это предотвращает дубликаты.

---

### 5. Сохранение погоды отдельно (LuggifyRepository.kt)

Метод для сохранения только погоды:

```kotlin
suspend fun saveWeatherLocally(slug: String, forecast: List<DailyForecast>) {
    // 1. Находим чеклист
    val checklist = localStore.getChecklist(slug) ?: return
    
    // 2. Добавляем погоду
    val updated = checklist.copy(daily_forecast = forecast)
    
    // 3. Сохраняем
    localStore.saveChecklist(updated)
}
```

**Суть:** Обновляем только поле `daily_forecast`, не трогая остальные данные.

---

### 6. Автозагрузка погоды при входе (ChecklistScreen.kt)

```kotlin
@Composable
fun ChecklistScreen(slug: String, viewModel: LuggifyViewModel, ...) {
    
    // При каждом входе на экран
    LaunchedEffect(Unit) {
        viewModel.tryLoadWeather()  // Проверит и загрузит если нужно
    }
    
    // ... остальной UI
}
```

**Суть:** `LaunchedEffect(Unit)` срабатывает один раз при входе на экран.

---

### 7. Проверка сети (NetworkUtils.kt)

```kotlin
object NetworkUtils {
    fun isNetworkAvailable(context: Context): Boolean {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) 
            as ConnectivityManager
            
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
```

**Суть:** Проверяет, есть ли активное интернет-соединение.

---

## Поток данных (визуализация)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ПОЛЬЗОВАТЕЛЬ ОТКРЫВАЕТ ЧЕКЛИСТ               │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  ChecklistScreen: LaunchedEffect(Unit) → tryLoadWeather()      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  ViewModel: refreshWeatherForecast()                            │
│  (всегда пытаемся обновить погоду)                              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  ViewModel: Есть сеть?                                          │
│  ├─ ДА → запрос к серверу                                       │
│  └─ НЕТ → выход (показываем что есть)                           │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository: generatePackingList(saveLocally = false)          │
│  → API запрос → получаем чеклист с погодой                      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  ViewModel: Обновляем UI (добавляем погоду в текущий чеклист)  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository: saveWeatherLocally() → сохраняем в DataStore      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  ГОТОВО: Погода отображается и сохранена для оффлайн           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Итого

| Действие | Онлайн | Оффлайн |
|----------|--------|---------|
| Просмотр чеклистов | ✅ С сервера + кэш | ✅ Из кэша |
| Просмотр погоды | ✅ Актуальная | ✅ Сохранённая |
| Создание чеклиста | ✅ | ❌ |
| Редактирование | ✅ Синхронизируется | ✅ Локально |
| Удаление | ✅ Синхронизируется | ✅ Локально |
| Сохранение в "Мои" | ✅ | ❌ |
