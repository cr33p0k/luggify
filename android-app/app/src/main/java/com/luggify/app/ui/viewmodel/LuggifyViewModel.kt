package com.luggify.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.luggify.app.data.datastore.UserPreferencesDataStore
import com.luggify.app.data.models.City
import com.luggify.app.data.models.Checklist
import com.luggify.app.data.models.PackingRequest
import com.luggify.app.data.repository.LuggifyRepository
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
    val isFromMyChecklists: Boolean = false
)

class LuggifyViewModel(
    private val repository: LuggifyRepository = LuggifyRepository(),
    private val userId: String = "",
    private val userPreferencesDataStore: UserPreferencesDataStore? = null
) : ViewModel() {

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()
    
    init {
        // Загружаем сохраненные данные при инициализации
        loadSavedPreferences()
    }
    
    private fun loadSavedPreferences() {
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                try {
                    val savedCity = dataStore.getCity()
                    val savedStartDate = dataStore.getStartDate()
                    val savedEndDate = dataStore.getEndDate()
                    
                    _uiState.value = _uiState.value.copy(
                        selectedCity = savedCity,
                        startDate = savedStartDate,
                        endDate = savedEndDate
                    )
                } catch (e: Exception) {
                    // Игнорируем ошибки при загрузке сохраненных данных
                }
            }
        }
    }

    fun searchCities(query: String) {
        if (query.isEmpty()) {
            _uiState.value = _uiState.value.copy(
                cities = emptyList(),
                isLoadingCities = false
            )
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingCities = true)
            repository.getCities(query).fold(
                onSuccess = { cities ->
                    _uiState.value = _uiState.value.copy(
                        cities = cities,
                        isLoadingCities = false,
                        error = null
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        error = error.message,
                        cities = emptyList(),
                        isLoadingCities = false
                    )
                }
            )
        }
    }

    fun selectCity(city: City) {
        _uiState.value = _uiState.value.copy(
            selectedCity = city,
            cities = emptyList(),
            isLoadingCities = false
        )
        // Сохраняем выбранный город
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                dataStore.saveCity(city)
            }
        }
    }
    
    fun clearCity() {
        _uiState.value = _uiState.value.copy(
            selectedCity = null,
            cities = emptyList(),
            isLoadingCities = false
        )
        // Очищаем сохраненный город
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                dataStore.clearCity()
            }
        }
    }

    fun setStartDate(date: Date) {
        _uiState.value = _uiState.value.copy(startDate = date)
        // Сохраняем дату начала
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                dataStore.saveStartDate(date)
            }
        }
    }

    fun setEndDate(date: Date) {
        _uiState.value = _uiState.value.copy(endDate = date)
        // Сохраняем дату окончания
        userPreferencesDataStore?.let { dataStore ->
            viewModelScope.launch {
                dataStore.saveEndDate(date)
            }
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
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        checklist = checklist,
                        error = null,
                        checkedItems = emptySet(),
                        removedItems = emptySet(),
                        addedItems = emptyList(),
                        isDirty = false,
                        isFromMyChecklists = false // Новый чеклист
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
        _uiState.value = _uiState.value.copy(isLoading = true, error = null)

        viewModelScope.launch {
            repository.getChecklist(slug).fold(
                onSuccess = { checklist ->
                    val checkedItemsSet = checklist.checked_items?.toSet() ?: emptySet()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        checklist = checklist,
                        error = null,
                        checkedItems = checkedItemsSet,
                        removedItems = checklist.removed_items?.toSet() ?: emptySet(),
                        addedItems = checklist.added_items ?: emptyList(),
                        isDirty = false,
                        isFromMyChecklists = fromMyChecklists
                    )
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
        if (currentChecked.remove(item).not()) {
            currentChecked.add(item)
        }
        _uiState.value = _uiState.value.copy(
            checkedItems = currentChecked,
            isDirty = true
        )
    }

    fun removeItem(item: String) {
        val currentChecked = _uiState.value.checkedItems.toMutableSet()
        currentChecked.remove(item)
        
        // Если элемент был добавлен пользователем, удаляем его из addedItems
        val currentAddedItems = _uiState.value.addedItems.toMutableList()
        val isAddedByUser = currentAddedItems.contains(item)
        
        if (isAddedByUser) {
            // Удаляем из списка добавленных пользователем вещей
            currentAddedItems.remove(item)
            _uiState.value = _uiState.value.copy(
                addedItems = currentAddedItems,
                checkedItems = currentChecked,
                isDirty = true
            )
        } else {
            // Если это оригинальная вещь из чеклиста, добавляем в removedItems
            val currentRemoved = _uiState.value.removedItems.toMutableSet()
            currentRemoved.add(item)
            _uiState.value = _uiState.value.copy(
                removedItems = currentRemoved,
                checkedItems = currentChecked,
                isDirty = true
            )
        }
    }

    fun resetCheckedItems() {
        _uiState.value = _uiState.value.copy(
            checkedItems = emptySet(),
            isDirty = true
        )
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
                _uiState.value = _uiState.value.copy(
                    addedItems = currentAddedItems,
                    newItemText = "",
                    showAddItemDialog = false,
                    isDirty = true
                )
            }
        }
    }

    fun saveChecklistState() {
        val checklist = _uiState.value.checklist ?: return
        val slug = checklist.slug

        viewModelScope.launch {
            val state = com.luggify.app.data.models.ChecklistStateUpdate(
                checked_items = _uiState.value.checkedItems.toList(),
                removed_items = _uiState.value.removedItems.toList(),
                added_items = _uiState.value.addedItems,
                items = checklist.items
            )

            repository.updateChecklistState(slug, state).fold(
                onSuccess = { updatedChecklist ->
                    // Сохраняем текущий прогноз погоды из состояния
                    val currentForecast = _uiState.value.checklist?.daily_forecast
                    val checkedItemsSet = updatedChecklist.checked_items?.toSet() ?: emptySet()
                    _uiState.value = _uiState.value.copy(
                        checklist = updatedChecklist.copy(
                            daily_forecast = currentForecast // Сохраняем прогноз погоды
                        ),
                        checkedItems = checkedItemsSet,
                        removedItems = updatedChecklist.removed_items?.toSet() ?: emptySet(),
                        addedItems = updatedChecklist.added_items ?: emptyList(),
                        isDirty = false,
                        saveStateSuccess = true
                    )
                    // Скрываем сообщение через 1.5 секунды
                    hideMessageAfterDelay { copy(saveStateSuccess = false) }
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        error = error.message ?: "Ошибка при сохранении"
                    )
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun navigateBack() {
        _uiState.value = _uiState.value.copy(
            checklist = null,
            checkedItems = emptySet(),
            removedItems = emptySet(),
            addedItems = emptyList(),
            isDirty = false,
            isFromMyChecklists = false
        )
    }

    fun loadMyChecklists() {
        if (userId.isEmpty()) return
        
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingChecklists = true, error = null)
            
            repository.getMyChecklists(userId).fold(
                onSuccess = { checklists ->
                    _uiState.value = _uiState.value.copy(
                        myChecklists = checklists,
                        isLoadingChecklists = false,
                        error = null
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        isLoadingChecklists = false,
                        error = error.message ?: "Ошибка при загрузке чеклистов"
                    )
                }
            )
        }
    }

    fun saveCurrentChecklist() {
        val checklist = _uiState.value.checklist ?: return
        if (userId.isEmpty()) return

        viewModelScope.launch {
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

            repository.saveChecklist(checklistCreate).fold(
                onSuccess = { savedChecklist ->
                    // Сохраняем текущий прогноз погоды из состояния
                    val currentForecast = _uiState.value.checklist?.daily_forecast
                    _uiState.value = _uiState.value.copy(
                        checklist = savedChecklist.copy(
                            daily_forecast = currentForecast // Сохраняем прогноз погоды
                        ),
                        error = null,
                        saveSuccess = true
                    )
                    loadMyChecklists() // Обновляем список чеклистов
                    // Скрываем сообщение через 1.5 секунды
                    hideMessageAfterDelay { copy(saveSuccess = false) }
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        error = error.message ?: "Ошибка при сохранении чеклиста"
                    )
                }
            )
        }
    }

    fun deleteChecklist(slug: String) {
        viewModelScope.launch {
            repository.deleteChecklist(slug).fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(
                        myChecklists = _uiState.value.myChecklists.filter { it.slug != slug },
                        error = null
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        error = error.message ?: "Ошибка при удалении чеклиста"
                    )
                }
            )
        }
    }

    fun openChecklistFromMyList(checklist: Checklist) {
        _uiState.value = _uiState.value.copy(
            checklist = checklist,
            checkedItems = checklist.checked_items?.toSet() ?: emptySet(),
            removedItems = checklist.removed_items?.toSet() ?: emptySet(),
            addedItems = checklist.added_items ?: emptyList(),
            isDirty = false,
            isFromMyChecklists = true // Чеклист открыт из "Мои чеклисты"
        )
        // Подгружаем актуальный прогноз погоды (как в TMA)
        refreshWeatherForecast(checklist.city, checklist.start_date, checklist.end_date)
    }
    
    private fun refreshWeatherForecast(city: String, startDate: String, endDate: String) {
        val request = PackingRequest(
            city = city,
            start_date = startDate,
            end_date = endDate
        )
        
        viewModelScope.launch {
            repository.generatePackingList(request).fold(
                onSuccess = { checklistWithForecast ->
                    // Обновляем только daily_forecast, остальное не трогаем
                    _uiState.value.checklist?.let { currentChecklist ->
                        _uiState.value = _uiState.value.copy(
                            checklist = currentChecklist.copy(
                                daily_forecast = checklistWithForecast.daily_forecast
                            )
                        )
                    }
                },
                onFailure = {
                    // Игнорируем ошибки при загрузке прогноза, основной чеклист уже загружен
                }
            )
        }
    }
    
    private fun hideMessageAfterDelay(update: UiState.() -> UiState) {
        viewModelScope.launch {
            kotlinx.coroutines.delay(1500)
            _uiState.value = _uiState.value.update()
        }
    }
}

