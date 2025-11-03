package com.luggify.app.data.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.luggify.app.data.models.City
import kotlinx.coroutines.flow.first
import java.util.Date

// Создаем DataStore для хранения настроек
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "user_preferences")

// Ключи для сохранения данных
private val CITY_KEY = stringPreferencesKey("selected_city")
private val START_DATE_KEY = longPreferencesKey("start_date")
private val END_DATE_KEY = longPreferencesKey("end_date")

// Простой класс для работы с сохраненными данными
class UserPreferencesDataStore(private val context: Context) {
    private val gson = Gson()
    
    // Получить сохраненный город
    suspend fun getCity(): City? {
        val preferences = context.dataStore.data.first()
        return preferences[CITY_KEY]?.let { cityJson ->
            try {
                gson.fromJson(cityJson, City::class.java)
            } catch (e: Exception) {
                null
            }
        }
    }
    
    // Получить сохраненную дату начала
    suspend fun getStartDate(): Date? {
        val preferences = context.dataStore.data.first()
        return preferences[START_DATE_KEY]?.let { Date(it) }
    }
    
    // Получить сохраненную дату окончания
    suspend fun getEndDate(): Date? {
        val preferences = context.dataStore.data.first()
        return preferences[END_DATE_KEY]?.let { Date(it) }
    }
    
    // Сохранить город
    suspend fun saveCity(city: City) {
        context.dataStore.edit { preferences ->
            preferences[CITY_KEY] = gson.toJson(city)
        }
    }
    
    // Сохранить дату начала
    suspend fun saveStartDate(date: Date) {
        context.dataStore.edit { preferences ->
            preferences[START_DATE_KEY] = date.time
        }
    }
    
    // Сохранить дату окончания
    suspend fun saveEndDate(date: Date) {
        context.dataStore.edit { preferences ->
            preferences[END_DATE_KEY] = date.time
        }
    }
    
    // Очистить сохраненный город
    suspend fun clearCity() {
        context.dataStore.edit { preferences ->
            preferences.remove(CITY_KEY)
        }
    }
}

