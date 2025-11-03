package com.luggify.app.data.repository

import com.luggify.app.data.api.ApiClient
import com.luggify.app.data.models.Checklist
import com.luggify.app.data.models.ChecklistStateUpdate
import com.luggify.app.data.models.City
import com.luggify.app.data.models.PackingRequest
import com.luggify.app.data.models.ChecklistCreate
import retrofit2.Response
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.io.IOException

class LuggifyRepository {
    private val api = ApiClient.api
    
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

    suspend fun generatePackingList(request: PackingRequest): Result<Checklist> {
        return handleApiCall(
            call = { api.generatePackingList(request) },
            errorMessage = "Ошибка генерации списка"
        )
    }

    suspend fun getChecklist(slug: String): Result<Checklist> {
        return handleApiCall(
            call = { api.getChecklist(slug) },
            errorMessage = "Чеклист не найден"
        )
    }

    suspend fun updateChecklistState(slug: String, state: ChecklistStateUpdate): Result<Checklist> {
        return handleApiCall(
            call = { api.updateChecklistState(slug, state) },
            errorMessage = "Ошибка обновления"
        )
    }

    suspend fun deleteChecklist(slug: String): Result<Unit> {
        return try {
            val response = api.deleteChecklist(slug)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorBody = try {
                    response.errorBody()?.string() ?: "Неизвестная ошибка"
                } catch (e: Exception) {
                    "Ошибка чтения ответа"
                }
                Result.failure(Exception("Ошибка удаления (${response.code()}): $errorBody"))
            }
        } catch (e: SocketTimeoutException) {
            Result.failure(Exception("Таймаут соединения. Сервер не отвечает. Попробуйте позже."))
        } catch (e: UnknownHostException) {
            Result.failure(Exception("Не удалось подключиться к серверу. Проверьте интернет соединение."))
        } catch (e: IOException) {
            Result.failure(Exception("Ошибка сети: ${e.message}"))
        } catch (e: Exception) {
            Result.failure(Exception("Ошибка удаления: ${e.message}"))
        }
    }

    suspend fun getMyChecklists(userId: String): Result<List<Checklist>> {
        return handleApiCall(
            call = { api.getMyChecklists(userId) },
            errorMessage = "Ошибка загрузки чеклистов"
        )
    }

    suspend fun saveChecklist(checklist: ChecklistCreate): Result<Checklist> {
        return handleApiCall(
            call = { api.saveChecklist(checklist) },
            errorMessage = "Ошибка сохранения"
        )
    }
}

