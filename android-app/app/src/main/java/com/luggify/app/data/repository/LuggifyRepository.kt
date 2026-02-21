package com.luggify.app.data.repository

import android.content.Context
import com.luggify.app.data.api.ApiClient
import com.luggify.app.data.datastore.ChecklistDataStore
import com.luggify.app.data.models.Checklist
import com.luggify.app.data.models.ChecklistStateUpdate
import com.luggify.app.data.models.City
import com.luggify.app.data.models.PackingRequest
import com.luggify.app.data.models.ChecklistCreate
import retrofit2.Response
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.io.IOException

class LuggifyRepository(context: Context) {
    private val api = ApiClient.api
    private val localStore = ChecklistDataStore(context)
    
    private suspend fun <T> handleApiCall(
        call: suspend () -> Response<T>,
        errorMessage: String
    ): Result<T> {
        return try {
            val response = call()
            when {
                response.isSuccessful && response.body() != null -> {
                    Result.success(response.body()!!)
                }
                else -> {
                    val errorBody = try {
                        response.errorBody()?.string() ?: "Неизвестная ошибка"
                    } catch (e: Exception) {
                        "Ошибка чтения ответа"
                    }
                    Result.failure(Exception("$errorMessage (${response.code()}): $errorBody"))
                }
            }
        } catch (e: SocketTimeoutException) {
            Result.failure(Exception("Таймаут соединения. Сервер не отвечает. Попробуйте позже."))
        } catch (e: UnknownHostException) {
            Result.failure(Exception("Не удалось подключиться к серверу. Проверьте интернет соединение."))
        } catch (e: IOException) {
            Result.failure(Exception("Ошибка сети: ${e.message}"))
        } catch (e: Exception) {
            Result.failure(Exception("$errorMessage: ${e.message}"))
        }
    }

    suspend fun getCities(query: String): Result<List<City>> {
        val trimmedQuery = query.trim()
        if (trimmedQuery.isEmpty()) {
            return Result.success(emptyList())
        }
        
        return handleApiCall(
            call = { api.getCities(trimmedQuery) },
            errorMessage = "Ошибка загрузки городов"
        )
    }

    /**
     * Генерирует список вещей для поездки
     * @param saveLocally false = только получить данные (для обновления погоды существующего чеклиста)
     */
    suspend fun generatePackingList(request: PackingRequest, saveLocally: Boolean = true): Result<Checklist> {
        val result = handleApiCall(
            call = { api.generatePackingList(request) },
            errorMessage = "Ошибка генерации списка"
        )
        
        if (saveLocally) {
            result.onSuccess { checklist ->
                // Сохраняем С погодой
                localStore.saveChecklist(checklist)
            }
        }
        
        return result
    }

    suspend fun getChecklist(slug: String): Result<Checklist> {
        val result = handleApiCall(
            call = { api.getChecklist(slug) },
            errorMessage = "Чеклист не найден"
        )
        
        return result.fold(
            onSuccess = { checklist ->
                // Сохраняем локально (сервер не возвращает погоду, сохраняем из локальной версии)
                val localChecklist = localStore.getChecklist(slug)
                val checklistToSave = if (checklist.daily_forecast == null && localChecklist?.daily_forecast != null) {
                    checklist.copy(daily_forecast = localChecklist.daily_forecast)
                } else {
                    checklist
                }
                localStore.saveChecklist(checklistToSave)
                Result.success(checklistToSave)
            },
            onFailure = { error ->
                val localChecklist = localStore.getChecklist(slug)
                if (localChecklist != null) {
                    Result.success(localChecklist)
                } else {
                    Result.failure(error)
                }
            }
        )
    }

    suspend fun updateChecklistState(slug: String, state: ChecklistStateUpdate): Result<Checklist> {
        // Сначала сохраняем локально с needsSync = true (потом обновим при успехе)
        val localChecklist = localStore.updateChecklistState(
            slug = slug,
            checkedItems = state.checked_items,
            removedItems = state.removed_items,
            addedItems = state.added_items,
            items = state.items,
            needsSync = true // Пока синхронизация не прошла
        )
        
        if (localChecklist == null) {
            return Result.failure(Exception("Чеклист не найден локально"))
        }
        
        val result = handleApiCall(
            call = { api.updateChecklistState(slug, state) },
            errorMessage = "Ошибка обновления"
        )
        
        return result.fold(
            onSuccess = { checklist ->
                // Успешная синхронизация - needsSync = false
                val checklistWithForecast = checklist.copy(
                    daily_forecast = localChecklist.daily_forecast,
                    needsSync = false
                )
                localStore.saveChecklist(checklistWithForecast)
                Result.success(checklistWithForecast)
            },
            onFailure = { _ ->
                // Нет сети — возвращаем локальную версию с needsSync = true
                val offlineChecklist = localChecklist.copy(needsSync = true)
                localStore.saveChecklist(offlineChecklist)
                Result.success(offlineChecklist)
            }
        )
    }
    
    /**
     * Синхронизировать текущее состояние чеклиста с сервером
     * Вызывается автоматически при входе в чеклист (если needsSync = true)
     * @return true если синхронизация прошла успешно, false при ошибке, null если чеклист не найден
     */
    suspend fun syncChecklist(slug: String): Result<Checklist>? {
        val checklist = localStore.getChecklist(slug) ?: return null
        
        // Если синхронизация не требуется, возвращаем текущий чеклист
        if (!checklist.needsSync) {
            return Result.success(checklist)
        }
        
        val state = ChecklistStateUpdate(
            checked_items = checklist.checked_items,
            removed_items = checklist.removed_items,
            added_items = checklist.added_items,
            items = checklist.items
        )
        
        val result = handleApiCall(
            call = { api.updateChecklistState(slug, state) },
            errorMessage = "Ошибка синхронизации"
        )
        
        return result.fold(
            onSuccess = { serverChecklist ->
                // Успешная синхронизация — needsSync = false
                val synced = serverChecklist.copy(
                    daily_forecast = checklist.daily_forecast,
                    needsSync = false
                )
                localStore.saveChecklist(synced)
                Result.success(synced)
            },
            onFailure = { error ->
                Result.failure(error)
            }
        )
    }
    
    /**
     * Проверить, требуется ли синхронизация для чеклиста
     */
    suspend fun checkNeedsSync(slug: String): Boolean {
        return localStore.getChecklist(slug)?.needsSync ?: false
    }

    suspend fun deleteChecklist(slug: String): Result<Unit> {
        localStore.deleteChecklist(slug)
        
        return try {
            api.deleteChecklist(slug)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.success(Unit)
        }
    }

    suspend fun getMyChecklists(userId: String): Result<List<Checklist>> {
        val localChecklists = localStore.getAllChecklists()
        
        val result = handleApiCall(
            call = { api.getMyChecklists(userId) },
            errorMessage = "Ошибка загрузки чеклистов"
        )
        
        return result.fold(
            onSuccess = { serverChecklists ->
                // Создаём карту локальных чеклистов для быстрого поиска
                val localMap = localChecklists.associateBy { it.slug }
                
                val mergedChecklists = serverChecklists.map { serverChecklist ->
                    val localChecklist = localMap[serverChecklist.slug]
                    
                    // Если локальный чеклист имеет несинхронизированные изменения,
                    // используем локальные данные вместо серверных
                    if (localChecklist != null && localChecklist.needsSync) {
                        // Сохраняем локальные изменения, но обновляем базовые данные с сервера
                        localChecklist.copy(
                            // Базовые данные могут обновиться на сервере (например, items)
                            // но состояние (checked, removed, added) сохраняем локальное
                            needsSync = true
                        )
                    } else {
                        // Нет локальных несинхронизированных изменений — берём с сервера
                        serverChecklist.copy(
                            daily_forecast = localChecklist?.daily_forecast ?: serverChecklist.daily_forecast,
                            needsSync = false
                        )
                    }
                }
                localStore.saveAllChecklists(mergedChecklists)
                Result.success(mergedChecklists)
            },
            onFailure = { error ->
                if (localChecklists.isNotEmpty()) {
                    Result.success(localChecklists)
                } else {
                    Result.failure(error)
                }
            }
        )
    }

    suspend fun saveChecklist(checklist: ChecklistCreate, oldSlug: String? = null): Result<Checklist> {
        val result = handleApiCall(
            call = { api.saveChecklist(checklist) },
            errorMessage = "Ошибка сохранения"
        )
        
        result.onSuccess { savedChecklist ->
            if (oldSlug != null && oldSlug != savedChecklist.slug) {
                localStore.deleteChecklist(oldSlug)
            }
            localStore.saveChecklist(savedChecklist)
        }
        
        return result
    }
    
    /**
     * Сохранить погоду для чеклиста локально
     */
    suspend fun saveWeatherLocally(slug: String, forecast: List<com.luggify.app.data.models.DailyForecast>) {
        val checklist = localStore.getChecklist(slug) ?: return
        val updated = checklist.copy(daily_forecast = forecast)
        localStore.saveChecklist(updated)
    }
    
    suspend fun getLocalChecklists(): List<Checklist> {
        return localStore.getAllChecklists()
    }
    
    suspend fun deleteChecklistLocally(slug: String) {
        localStore.deleteChecklist(slug)
    }
    
    /**
     * Синхронизировать все чеклисты с needsSync = true
     * Вызывается при загрузке списка "Мои чеклисты" когда есть интернет
     * @return список обновлённых чеклистов
     */
    suspend fun syncAllPendingChecklists(): List<Checklist> {
        val allChecklists = localStore.getAllChecklists()
        val pendingChecklists = allChecklists.filter { it.needsSync }
        
        if (pendingChecklists.isEmpty()) {
            return allChecklists
        }
        
        val updatedChecklists = allChecklists.toMutableList()
        
        for (checklist in pendingChecklists) {
            val state = ChecklistStateUpdate(
                checked_items = checklist.checked_items,
                removed_items = checklist.removed_items,
                added_items = checklist.added_items,
                items = checklist.items
            )
            
            val result = handleApiCall(
                call = { api.updateChecklistState(checklist.slug, state) },
                errorMessage = "Ошибка синхронизации"
            )
            
            result.onSuccess { serverChecklist ->
                // Успешная синхронизация — обновляем в списке
                val index = updatedChecklists.indexOfFirst { it.slug == checklist.slug }
                if (index != -1) {
                    updatedChecklists[index] = serverChecklist.copy(
                        daily_forecast = checklist.daily_forecast,
                        needsSync = false
                    )
                }
            }
            // При ошибке — чеклист остаётся с needsSync = true
        }
        
        // Сохраняем обновлённый список
        localStore.saveAllChecklists(updatedChecklists)
        return updatedChecklists
    }
}
