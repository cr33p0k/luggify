package com.luggify.app.data.models

data class Checklist(
    val slug: String,
    val city: String,
    val start_date: String,
    val end_date: String,
    val items: List<String>,
    val items_by_category: Map<String, List<String>>? = null,
    val avg_temp: Double? = null,
    val conditions: List<String>? = null,
    val daily_forecast: List<DailyForecast>? = null,
    val checked_items: List<String>? = null,
    val removed_items: List<String>? = null,
    val added_items: List<String>? = null
)

data class PackingRequest(
    val city: String,
    val start_date: String,
    val end_date: String
)

data class ChecklistStateUpdate(
    val checked_items: List<String>? = null,
    val removed_items: List<String>? = null,
    val added_items: List<String>? = null,
    val items: List<String>? = null
)

data class DailyForecast(
    val date: String,
    val temp_min: Double,
    val temp_max: Double,
    val condition: String,
    val icon: String
)

data class ChecklistCreate(
    val city: String,
    val start_date: String,
    val end_date: String,
    val items: List<String>,
    val avg_temp: Double? = null,
    val conditions: List<String>? = null,
    val checked_items: List<String>? = null,
    val removed_items: List<String>? = null,
    val added_items: List<String>? = null,
    val tg_user_id: String
)

