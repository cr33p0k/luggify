package com.luggify.app.data.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.luggify.app.data.models.Checklist
import kotlinx.coroutines.flow.first

// Создаем отдельный DataStore для чеклистов
private val Context.checklistDataStore: DataStore<Preferences> by preferencesDataStore(name = "checklists")

// Ключи для хранения чеклистов
private val CHECKLISTS_KEY = stringPreferencesKey("all_checklists")

/**
 * Локальное хранилище для чеклистов
 * Сохраняет чеклисты локально и позволяет работать оффлайн
 */
class ChecklistDataStore(private val context: Context) {
    private val gson = Gson()
    
    /**
     * Получить все сохраненные чеклисты
     */
    suspend fun getAllChecklists(): List<Checklist> {
        val preferences = context.checklistDataStore.data.first()
        return preferences[CHECKLISTS_KEY]?.let { checklistsJson ->
            try {
                val type = object : TypeToken<List<Checklist>>() {}.type
                gson.fromJson<List<Checklist>>(checklistsJson, type) ?: emptyList()
            } catch (e: Exception) {
                emptyList()
            }
        } ?: emptyList()
    }
    
    /**
     * Получить чеклист по slug
     */
    suspend fun getChecklist(slug: String): Checklist? {
        val checklists = getAllChecklists()
        return checklists.find { it.slug == slug }
    }
    
    /**
     * Сохранить один чеклист (добавить или обновить)
     */
    suspend fun saveChecklist(checklist: Checklist) {
        val currentChecklists = getAllChecklists().toMutableList()
        
        // Удалить старую версию, если существует
        val existingIndex = currentChecklists.indexOfFirst { it.slug == checklist.slug }
        if (existingIndex != -1) {
            currentChecklists[existingIndex] = checklist
        } else {
            currentChecklists.add(0, checklist) // Добавить в начало списка
        }
        
        saveAllChecklists(currentChecklists)
    }
    
    /**
     * Сохранить все чеклисты (перезаписать)
     */
    suspend fun saveAllChecklists(checklists: List<Checklist>) {
        context.checklistDataStore.edit { preferences ->
            preferences[CHECKLISTS_KEY] = gson.toJson(checklists)
        }
    }
    
    /**
     * Удалить чеклист
     */
    suspend fun deleteChecklist(slug: String) {
        val currentChecklists = getAllChecklists().toMutableList()
        currentChecklists.removeAll { it.slug == slug }
        saveAllChecklists(currentChecklists)
    }
    
    /**
     * Обновить состояние чеклиста (отмеченные, удаленные, добавленные элементы)
     * @param needsSync true если изменения сделаны оффлайн и требуют синхронизации
     */
    suspend fun updateChecklistState(
        slug: String,
        checkedItems: List<String>? = null,
        removedItems: List<String>? = null,
        addedItems: List<String>? = null,
        items: List<String>? = null,
        needsSync: Boolean? = null
    ): Checklist? {
        val checklist = getChecklist(slug) ?: return null
        
        val updatedChecklist = checklist.copy(
            checked_items = checkedItems ?: checklist.checked_items,
            removed_items = removedItems ?: checklist.removed_items,
            added_items = addedItems ?: checklist.added_items,
            items = items ?: checklist.items,
            needsSync = needsSync ?: checklist.needsSync
        )
        
        saveChecklist(updatedChecklist)
        return updatedChecklist
    }
    
    /**
     * Обновить флаг синхронизации для чеклиста
     */
    suspend fun setNeedsSync(slug: String, needsSync: Boolean): Checklist? {
        val checklist = getChecklist(slug) ?: return null
        val updatedChecklist = checklist.copy(needsSync = needsSync)
        saveChecklist(updatedChecklist)
        return updatedChecklist
    }
    
    /**
     * Очистить все чеклисты
     */
    suspend fun clearAllChecklists() {
        context.checklistDataStore.edit { preferences ->
            preferences.clear()
        }
    }
}
