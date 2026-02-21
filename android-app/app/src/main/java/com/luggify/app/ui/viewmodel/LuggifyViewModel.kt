package com.luggify.app.ui.viewmodel

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.luggify.app.data.datastore.UserPreferencesDataStore
import com.luggify.app.data.models.City
import com.luggify.app.data.models.Checklist
import com.luggify.app.data.models.PackingRequest
import com.luggify.app.data.repository.LuggifyRepository
import com.luggify.app.utils.NetworkUtils
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class UiState(
    val isLoading: Boolean = false,
    val isLoadingCities: Boolean = false,
    val isLoadingChecklists: Boolean = false,
    val error: String? = null,
    val selectedCity: City? = null,
    val startDate: Date? = null,
    val endDate: Date? = null,
    val checklist: Checklist? = null,
    val checkedItems: Set<String> = emptySet(),
    val removedItems: Set<String> = emptySet(),
    val addedItems: List<String> = emptyList(),
    val cities: List<City> = emptyList(),
    val myChecklists: List<Checklist> = emptyList(),
    val showAddItemDialog: Boolean = false,
    val newItemText: String = "",
    val isDirty: Boolean = false,
    val saveStateSuccess: Boolean = false,
    val saveSuccess: Boolean = false,
    val isFromMyChecklists: Boolean = false,
    val defaultItems: List<String> = emptyList(),
    val isOfflineMode: Boolean = false
)

class LuggifyViewModel(
    context: Context,
    private val userId: String = "",
    private val userPreferencesDataStore: UserPreferencesDataStore? = null
) : ViewModel() {
    private val repository: LuggifyRepository = LuggifyRepository(context)
    private val appContext: Context = context.applicationContext

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()
    
    init {
        loadSavedPreferences()
    }
    
    private fun loadSavedPreferences() {
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                try {
                    val savedCity = dataStore.getCity()
                    val savedStartDate = dataStore.getStartDate()
                    val savedEndDate = dataStore.getEndDate()
                    val savedDefaultItems = dataStore.getDefaultItems()
                    
                    _uiState.value = _uiState.value.copy(
                        selectedCity = savedCity,
                        startDate = savedStartDate,
                        endDate = savedEndDate,
                        defaultItems = savedDefaultItems
                    )
                } catch (e: Exception) {
                    // Игнорируем ошибки
                }
            }
        }
    }

    fun searchCities(query: String) {
        if (query.isEmpty()) {
            _uiState.value = _uiState.value.copy(cities = emptyList(), isLoadingCities = false)
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingCities = true)
            repository.getCities(query).fold(
                onSuccess = { cities ->
                    _uiState.value = _uiState.value.copy(
                        cities = cities, isLoadingCities = false, error = null
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        error = error.message, cities = emptyList(), isLoadingCities = false
                    )
                }
            )
        }
    }

    fun selectCity(city: City) {
        _uiState.value = _uiState.value.copy(selectedCity = city, cities = emptyList(), isLoadingCities = false)
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch { dataStore.saveCity(city) }
        }
    }
    
    fun clearCity() {
        _uiState.value = _uiState.value.copy(selectedCity = null, cities = emptyList(), isLoadingCities = false)
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch { dataStore.clearCity() }
        }
    }

    fun setStartDate(date: Date) {
        _uiState.value = _uiState.value.copy(startDate = date)
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch { dataStore.saveStartDate(date) }
        }
    }

    fun setEndDate(date: Date) {
        _uiState.value = _uiState.value.copy(endDate = date)
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch { dataStore.saveEndDate(date) }
        }
    }

    fun generatePackingList() {
        val selectedCity = _uiState.value.selectedCity
        val startDate = _uiState.value.startDate
        val endDate = _uiState.value.endDate

        if (selectedCity == null || startDate == null || endDate == null) {
            _uiState.value = _uiState.value.copy(error = "Заполните все поля!")
            return
        }

        val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        val request = PackingRequest(
            city = selectedCity.fullName,
            start_date = dateFormat.format(startDate),
            end_date = dateFormat.format(endDate)
        )

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            repository.generatePackingList(request).fold(
                onSuccess = { checklist ->
                    val defaultItems = _uiState.value.defaultItems
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        checklist = checklist,
                        error = null,
                        checkedItems = emptySet(),
                        removedItems = emptySet(),
                        addedItems = defaultItems,
                        isDirty = defaultItems.isNotEmpty(),
                        isFromMyChecklists = false
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = error.message ?: "Ошибка при генерации списка"
                    )
                }
            )
        }
    }

    fun loadChecklist(slug: String, fromMyChecklists: Boolean = false) {
        // Если чеклист уже загружен, не загружаем заново
        if (_uiState.value.checklist?.slug == slug && !_uiState.value.isLoading) {
            return
        }
        
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)

        viewModelScope.launch {
            repository.getChecklist(slug).fold(
                onSuccess = { checklist ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        checklist = checklist,
                        error = null,
                        checkedItems = checklist.checked_items?.toSet() ?: emptySet(),
                        removedItems = checklist.removed_items?.toSet() ?: emptySet(),
                        addedItems = checklist.added_items ?: emptyList(),
                        isDirty = false,
                        isFromMyChecklists = fromMyChecklists,
                        saveStateSuccess = false  // Сбрасываем при загрузке
                    )
                    // Автоматически загружаем погоду
                    refreshWeatherForecast(checklist.city, checklist.start_date, checklist.end_date)
                    
                    // Если есть несинхронизированные изменения — пытаемся синхронизировать
                    if (checklist.needsSync) {
                        trySyncChecklist()
                    }
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = error.message ?: "Ошибка при загрузке чеклиста"
                    )
                }
            )
        }
    }

    fun toggleItemChecked(item: String) {
        val currentChecked = _uiState.value.checkedItems.toMutableSet()
        if (item in currentChecked) currentChecked.remove(item) else currentChecked.add(item)
        _uiState.value = _uiState.value.copy(checkedItems = currentChecked, isDirty = true)
    }

    fun removeItem(item: String) {
        val currentChecked = _uiState.value.checkedItems.toMutableSet()
        currentChecked.remove(item)
        
        val currentAddedItems = _uiState.value.addedItems.toMutableList()
        if (currentAddedItems.contains(item)) {
            currentAddedItems.remove(item)
            _uiState.value = _uiState.value.copy(addedItems = currentAddedItems, checkedItems = currentChecked, isDirty = true)
        } else {
            val currentRemoved = _uiState.value.removedItems.toMutableSet()
            currentRemoved.add(item)
            _uiState.value = _uiState.value.copy(removedItems = currentRemoved, checkedItems = currentChecked, isDirty = true)
        }
    }

    fun resetCheckedItems() {
        _uiState.value = _uiState.value.copy(checkedItems = emptySet(), isDirty = true)
    }

    fun showAddItemDialog() {
        _uiState.value = _uiState.value.copy(showAddItemDialog = true)
    }

    fun hideAddItemDialog() {
        _uiState.value = _uiState.value.copy(showAddItemDialog = false, newItemText = "")
    }

    fun setNewItemText(text: String) {
        _uiState.value = _uiState.value.copy(newItemText = text)
    }

    fun addNewItem() {
        val text = _uiState.value.newItemText.trim()
        if (text.isNotEmpty()) {
            val currentAddedItems = _uiState.value.addedItems.toMutableList()
            if (!currentAddedItems.contains(text)) {
                currentAddedItems.add(text)
                _uiState.value = _uiState.value.copy(addedItems = currentAddedItems, newItemText = "", showAddItemDialog = false, isDirty = true)
            }
        }
    }

    fun saveChecklistState() {
        val checklist = _uiState.value.checklist ?: return

        viewModelScope.launch {
            val state = com.luggify.app.data.models.ChecklistStateUpdate(
                checked_items = _uiState.value.checkedItems.toList(),
                removed_items = _uiState.value.removedItems.toList(),
                added_items = _uiState.value.addedItems,
                items = checklist.items
            )

            repository.updateChecklistState(checklist.slug, state).fold(
                onSuccess = { updatedChecklist ->
                    val currentForecast = _uiState.value.checklist?.daily_forecast
                    _uiState.value = _uiState.value.copy(
                        checklist = updatedChecklist.copy(daily_forecast = currentForecast),
                        checkedItems = updatedChecklist.checked_items?.toSet() ?: emptySet(),
                        removedItems = updatedChecklist.removed_items?.toSet() ?: emptySet(),
                        addedItems = updatedChecklist.added_items ?: emptyList(),
                        isDirty = false,
                        saveStateSuccess = true
                    )
                    hideMessageAfterDelay { copy(saveStateSuccess = false) }
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(error = error.message ?: "Ошибка при сохранении")
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun navigateBack() {
        _uiState.value = _uiState.value.copy(
            checklist = null, checkedItems = emptySet(), removedItems = emptySet(),
            addedItems = emptyList(), isDirty = false, isFromMyChecklists = false,
            saveStateSuccess = false, saveSuccess = false
        )
    }

    fun loadMyChecklists() {
        if (userId.isEmpty()) return
        
        viewModelScope.launch {
            // 1. Сразу показываем локальные данные
            val localChecklists = repository.getLocalChecklists()
            _uiState.value = _uiState.value.copy(
                myChecklists = localChecklists,
                isLoadingChecklists = false,
                error = null,
                isOfflineMode = false
            )
            
            // 2. Проверяем сеть
            val isNetworkAvailable = NetworkUtils.isNetworkAvailable(appContext)
            
            if (!isNetworkAvailable) {
                _uiState.value = _uiState.value.copy(isOfflineMode = true, error = null)
                return@launch
            }
            
            // 3. Есть сеть — сначала синхронизируем все несинхронизированные чеклисты
            val hasPendingSync = localChecklists.any { it.needsSync }
            if (hasPendingSync) {
                val syncedChecklists = repository.syncAllPendingChecklists()
                _uiState.value = _uiState.value.copy(
                    myChecklists = syncedChecklists,
                    error = null
                )
            }
            
            // 4. Загружаем актуальный список с сервера
            if (localChecklists.isEmpty()) {
                _uiState.value = _uiState.value.copy(isLoadingChecklists = true)
            }
            
            repository.getMyChecklists(userId).fold(
                onSuccess = { checklists ->
                    _uiState.value = _uiState.value.copy(
                        myChecklists = checklists,
                        isLoadingChecklists = false,
                        error = null,
                        isOfflineMode = false
                    )
                },
                onFailure = { _ ->
                    _uiState.value = _uiState.value.copy(isLoadingChecklists = false, isOfflineMode = true, error = null)
                }
            )
        }
    }

    fun saveCurrentChecklist() {
        val checklist = _uiState.value.checklist ?: return
        if (userId.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            
            val checklistCreate = com.luggify.app.data.models.ChecklistCreate(
                city = checklist.city,
                start_date = checklist.start_date,
                end_date = checklist.end_date,
                items = checklist.items,
                avg_temp = checklist.avg_temp,
                conditions = checklist.conditions,
                checked_items = _uiState.value.checkedItems.toList(),
                removed_items = _uiState.value.removedItems.toList(),
                added_items = _uiState.value.addedItems,
                tg_user_id = userId
            )

            // Передаем старый slug для удаления дубликата
            val oldSlug = checklist.slug
            
            repository.saveChecklist(checklistCreate, oldSlug).fold(
                onSuccess = { savedChecklist ->
                    val currentForecast = _uiState.value.checklist?.daily_forecast
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        checklist = savedChecklist.copy(daily_forecast = currentForecast),
                        error = null,
                        saveSuccess = true,
                        isFromMyChecklists = true,
                        isDirty = false
                    )
                    loadMyChecklists()
                    hideMessageAfterDelay { copy(saveSuccess = false) }
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = error.message ?: "Ошибка при сохранении чеклиста"
                    )
                }
            )
        }
    }

    fun deleteChecklist(slug: String) {
        viewModelScope.launch {
            repository.deleteChecklist(slug)
            val updatedChecklists = repository.getLocalChecklists()
            _uiState.value = _uiState.value.copy(myChecklists = updatedChecklists, error = null)
        }
    }

    fun openChecklistFromMyList(checklist: Checklist) {
        _uiState.value = _uiState.value.copy(
            checklist = checklist,
            checkedItems = checklist.checked_items?.toSet() ?: emptySet(),
            removedItems = checklist.removed_items?.toSet() ?: emptySet(),
            addedItems = checklist.added_items ?: emptyList(),
            isDirty = false,
            isFromMyChecklists = true
        )
        
        // Если есть несинхронизированные изменения — пытаемся синхронизировать
        if (checklist.needsSync) {
            trySyncChecklist()
        }
    }
    
    /**
     * Загрузить актуальную погоду для текущего чеклиста (если есть сеть)
     * Всегда обновляет погоду при наличии интернета, даже если есть кэшированная
     */
    fun tryLoadWeather() {
        val checklist = _uiState.value.checklist ?: return
        refreshWeatherForecast(checklist.city, checklist.start_date, checklist.end_date)
    }
    
    /**
     * Синхронизировать текущее состояние чеклиста с сервером
     * Вызывается автоматически при открытии чеклиста (если есть интернет и needsSync = true)
     * НЕ показывает сообщение "изменения сохранены" - это тихая синхронизация
     */
    fun trySyncChecklist() {
        val checklist = _uiState.value.checklist ?: return
        
        // Если синхронизация не требуется, пропускаем
        if (!checklist.needsSync) return
        
        val isNetworkAvailable = NetworkUtils.isNetworkAvailable(appContext)
        if (!isNetworkAvailable) return
        
        viewModelScope.launch {
            repository.syncChecklist(checklist.slug)?.fold(
                onSuccess = { syncedChecklist ->
                    // Синхронизация прошла успешно — обновляем чеклист с needsSync = false
                    val currentChecklist = _uiState.value.checklist
                    if (currentChecklist != null) {
                        _uiState.value = _uiState.value.copy(
                            checklist = syncedChecklist.copy(
                                daily_forecast = currentChecklist.daily_forecast,
                                needsSync = false
                            )
                        )
                        // Обновляем список чеклистов чтобы убрать значок синхронизации
                        loadMyChecklists()
                    }
                },
                onFailure = { /* Не удалось синхронизировать, попробуем позже */ }
            )
        }
    }
    
    private fun refreshWeatherForecast(city: String, startDate: String, endDate: String) {
        val isNetworkAvailable = NetworkUtils.isNetworkAvailable(appContext)
        if (!isNetworkAvailable) return
        
        val request = PackingRequest(city = city, start_date = startDate, end_date = endDate)
        
        viewModelScope.launch {
            // saveLocally = false - НЕ сохраняем новый чеклист, только получаем погоду
            repository.generatePackingList(request, saveLocally = false).fold(
                onSuccess = { checklistWithForecast ->
                    val currentChecklist = _uiState.value.checklist
                    if (currentChecklist != null && checklistWithForecast.daily_forecast != null) {
                        // Обновляем UI
                        _uiState.value = _uiState.value.copy(
                            checklist = currentChecklist.copy(daily_forecast = checklistWithForecast.daily_forecast)
                        )
                        // Сохраняем погоду локально для оффлайн доступа
                        repository.saveWeatherLocally(currentChecklist.slug, checklistWithForecast.daily_forecast)
                    }
                },
                onFailure = { _ -> /* Игнорируем ошибку */ }
            )
        }
    }
    
    private fun hideMessageAfterDelay(update: UiState.() -> UiState) {
        viewModelScope.launch {
            kotlinx.coroutines.delay(1500)
            _uiState.value = _uiState.value.update()
        }
    }
    
    fun addDefaultItem(item: String) {
        val currentDefaultItems = _uiState.value.defaultItems.toMutableList()
        if (!currentDefaultItems.contains(item)) {
            currentDefaultItems.add(item)
            _uiState.value = _uiState.value.copy(defaultItems = currentDefaultItems)
            userPreferencesDataStore?.let { dataStore ->
                viewModelScope.launch { dataStore.saveDefaultItems(currentDefaultItems) }
            }
        }
    }
    
    fun removeDefaultItem(item: String) {
        val currentDefaultItems = _uiState.value.defaultItems.toMutableList()
        currentDefaultItems.remove(item)
        _uiState.value = _uiState.value.copy(defaultItems = currentDefaultItems)
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch { dataStore.saveDefaultItems(currentDefaultItems) }
        }
    }
}
