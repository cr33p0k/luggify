package com.luggify.app.data.api

import com.luggify.app.data.models.Checklist
import com.luggify.app.data.models.ChecklistStateUpdate
import com.luggify.app.data.models.City
import com.luggify.app.data.models.PackingRequest
import com.luggify.app.data.models.ChecklistCreate
import retrofit2.Response
import retrofit2.http.*

interface LuggifyApi {
    @GET("geo/cities-autocomplete")
    suspend fun getCities(
        @Query("namePrefix") namePrefix: String
    ): Response<List<City>>

    @POST("generate-packing-list")
    suspend fun generatePackingList(
        @Body request: PackingRequest
    ): Response<Checklist>

    @GET("checklist/{slug}")
    suspend fun getChecklist(
        @Path("slug") slug: String
    ): Response<Checklist>

    @PATCH("checklist/{slug}/state")
    suspend fun updateChecklistState(
        @Path("slug") slug: String,
        @Body state: ChecklistStateUpdate
    ): Response<Checklist>

    @DELETE("checklist/{slug}")
    suspend fun deleteChecklist(
        @Path("slug") slug: String
    ): Response<Unit>

    @GET("tg-checklists/{user_id}")
    suspend fun getMyChecklists(
        @Path("user_id") userId: String
    ): Response<List<Checklist>>

    @POST("save-tg-checklist")
    suspend fun saveChecklist(
        @Body checklist: ChecklistCreate
    ): Response<Checklist>
}

