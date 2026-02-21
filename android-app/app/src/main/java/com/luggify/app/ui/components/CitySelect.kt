package com.luggify.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.luggify.app.data.models.City
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CitySelect(
    selectedCity: City?,
    cities: List<City>,
    isLoading: Boolean = false,
    onCitySelected: (City) -> Unit,
    onCityCleared: () -> Unit = {},
    onSearchQueryChanged: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var searchQuery by remember(selectedCity) { 
        mutableStateOf(selectedCity?.fullName ?: "") 
    }
    var showDropdown by remember { mutableStateOf(false) }
    
    // Функция для очистки города
    fun clearCity() {
        searchQuery = ""
        showDropdown = false
        onCityCleared()
    }
    
    // Debounce для поиска
    LaunchedEffect(searchQuery) {
        if (searchQuery != selectedCity?.fullName && searchQuery.isNotEmpty()) {
            delay(300) // Задержка 300мс перед поиском
            if (searchQuery.isNotEmpty()) {
                onSearchQueryChanged(searchQuery)
            }
        } else if (searchQuery.isEmpty()) {
            showDropdown = false
        }
    }
    
    // Показываем dropdown когда есть результаты или идет загрузка
    LaunchedEffect(cities, isLoading, searchQuery) {
        showDropdown = searchQuery.isNotEmpty() && (cities.isNotEmpty() || isLoading)
    }

    Box(modifier = modifier) {
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { query ->
                searchQuery = query
                if (query.isEmpty()) {
                    clearCity()
                }
            },
            label = { Text("Введите город") },
            placeholder = { Text("Начните вводить название города...") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Text,
                imeAction = ImeAction.Done
            ),
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(
                        onClick = { clearCity() }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Clear,
                            contentDescription = "Очистить"
                        )
                    }
                }
            },
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline
            )
        )

        // Dropdown с результатами поиска
        if (showDropdown) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 56.dp), // Отступ сверху чтобы не перекрывать поле ввода
                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            ) {
                if (isLoading) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.dp
                        )
                    }
                } else if (cities.isEmpty() && searchQuery.isNotEmpty()) {
                    Text(
                        text = "Город не найден",
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else if (cities.isNotEmpty()) {
                    LazyColumn(
                        modifier = Modifier
                            .heightIn(max = 250.dp)
                            .fillMaxWidth()
                    ) {
                        items(cities) { city ->
                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        onCitySelected(city)
                                        searchQuery = city.fullName
                                        showDropdown = false
                                    },
                                color = MaterialTheme.colorScheme.surface
                            ) {
                                Text(
                                    text = city.fullName,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                                    style = MaterialTheme.typography.bodyLarge
                                )
                            }
                            if (city != cities.last()) {
                                Divider(
                                    modifier = Modifier.padding(horizontal = 16.dp),
                                    color = MaterialTheme.colorScheme.outlineVariant
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

