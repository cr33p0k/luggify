package com.luggify.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.luggify.app.R
import com.luggify.app.ui.components.ChecklistItem
import com.luggify.app.ui.components.WeatherForecast
import com.luggify.app.ui.viewmodel.LuggifyViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChecklistScreen(
    slug: String,
    viewModel: LuggifyViewModel,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(slug) {
        if (uiState.checklist?.slug != slug) {
            viewModel.loadChecklist(slug)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_luggify_logo),
                            contentDescription = null,
                            modifier = Modifier.size(32.dp),
                            colorFilter = ColorFilter.tint(MaterialTheme.colorScheme.primary)
                        )
                        Text("Luggify")
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Назад"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.primary
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            when {
                uiState.isLoading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator()
                    }
                }

                uiState.error != null -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer
                        )
                    ) {
                        Text(
                            text = uiState.error ?: "Ошибка",
                            modifier = Modifier.padding(16.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            textAlign = TextAlign.Center
                        )
                    }
                }

                uiState.checklist != null -> {
                    val checklist = uiState.checklist!!
                    val visibleItems = checklist.items
                        .filter { !uiState.removedItems.contains(it) }
                        .plus(uiState.addedItems)

                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        item {
                            // Заголовок чеклиста
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 16.dp)
                            ) {
                                Text(
                                    text = checklist.city,
                                    style = MaterialTheme.typography.headlineMedium,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                Text(
                                    text = "${checklist.start_date} — ${checklist.end_date}",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                    modifier = Modifier.padding(top = 4.dp)
                                )
                            }
                        }

                        // Чеклист в карточке
                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.13f)
                                ),
                                border = androidx.compose.foundation.BorderStroke(
                                    3.dp,
                                    MaterialTheme.colorScheme.tertiary
                                ),
                                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    if (visibleItems.isEmpty()) {
                                        Column(
                                            horizontalAlignment = Alignment.CenterHorizontally,
                                            verticalArrangement = Arrangement.spacedBy(12.dp),
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(24.dp)
                                        ) {
                                            Image(
                                                painter = painterResource(id = R.drawable.ic_luggify_logo),
                                                contentDescription = null,
                                                modifier = Modifier.size(48.dp),
                                                colorFilter = ColorFilter.tint(
                                                    MaterialTheme.colorScheme.primary.copy(alpha = 0.4f)
                                                )
                                            )
                                            Text(
                                                text = "Чеклист пуст",
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                                                textAlign = TextAlign.Center
                                            )
                                        }
                                    } else {
                                        visibleItems.forEachIndexed { index, item ->
                                            key(item) {
                                                ChecklistItem(
                                                    item = item,
                                                    isChecked = uiState.checkedItems.contains(item),
                                                    onCheckedChange = { viewModel.toggleItemChecked(item) },
                                                    onRemove = { viewModel.removeItem(item) },
                                                    modifier = Modifier.fillMaxWidth()
                                                )
                                                if (index < visibleItems.size - 1) {
                                                    Divider(
                                                        modifier = Modifier.padding(vertical = 4.dp),
                                                        color = MaterialTheme.colorScheme.outlineVariant
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Кнопки управления
                        item {
                            Spacer(modifier = Modifier.height(16.dp))
                            
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Button(
                                    onClick = { viewModel.resetCheckedItems() },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = MaterialTheme.colorScheme.primary,
                                        contentColor = MaterialTheme.colorScheme.onPrimary
                                    )
                                ) {
                                    Text("Сбросить отметки")
                                }
                                
                                OutlinedButton(
                                    onClick = { viewModel.showAddItemDialog() },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.outlinedButtonColors(
                                        contentColor = MaterialTheme.colorScheme.primary
                                    )
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Add,
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("Добавить")
                                }
                            }

                            // Кнопка сохранения изменений
                            if (uiState.isDirty) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Button(
                                    onClick = { viewModel.saveChecklistState() },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = MaterialTheme.colorScheme.surface,
                                        contentColor = MaterialTheme.colorScheme.primary
                                    )
                                ) {
                                    Text("Сохранить изменения")
                                }
                            }
                            
                            if (uiState.saveStateSuccess) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = "Изменения сохранены!",
                                    color = MaterialTheme.colorScheme.primary,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                            
                            // Кнопка сохранения в "Мои чеклисты" (только если чеклист не из "Мои чеклисты")
                            if (!uiState.isFromMyChecklists) {
                                Spacer(modifier = Modifier.height(8.dp))
                                OutlinedButton(
                                    onClick = { viewModel.saveCurrentChecklist() },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = ButtonDefaults.outlinedButtonColors(
                                        contentColor = MaterialTheme.colorScheme.primary
                                    )
                                ) {
                                    Text("Сохранить в мои чеклисты")
                                }
                                
                                if (uiState.saveSuccess) {
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text(
                                        text = "Чеклист сохранён!",
                                        color = MaterialTheme.colorScheme.primary,
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier.fillMaxWidth()
                                    )
                                }
                            }
                        }

                        // Прогноз погоды
                        checklist.daily_forecast?.let { forecasts ->
                            item {
                                Spacer(modifier = Modifier.height(24.dp))
                                WeatherForecast(forecasts = forecasts)
                            }
                        }
                    }

                    // Диалог добавления вещи
                    if (uiState.showAddItemDialog) {
                        AlertDialog(
                            onDismissRequest = { viewModel.hideAddItemDialog() },
                            title = { Text("Добавить вещь") },
                            text = {
                                OutlinedTextField(
                                    value = uiState.newItemText,
                                    onValueChange = { viewModel.setNewItemText(it) },
                                    label = { Text("Новая вещь") },
                                    modifier = Modifier.fillMaxWidth(),
                                    singleLine = true
                                )
                            },
                            confirmButton = {
                                TextButton(
                                    onClick = {
                                        viewModel.addNewItem()
                                    }
                                ) {
                                    Text("Добавить")
                                }
                            },
                            dismissButton = {
                                TextButton(
                                    onClick = { viewModel.hideAddItemDialog() }
                                ) {
                                    Text("Отмена")
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}

