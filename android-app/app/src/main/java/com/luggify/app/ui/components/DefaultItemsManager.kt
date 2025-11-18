package com.luggify.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog

@Composable
fun DefaultItemsManager(
    defaultItems: List<String>,
    onAddItem: (String) -> Unit,
    onRemoveItem: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var showDialog by remember { mutableStateOf(false) }
    var newItemText by remember { mutableStateOf("") }

    OutlinedButton(
        onClick = { showDialog = true },
        modifier = modifier,
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = MaterialTheme.colorScheme.secondary
        )
    ) {
        Icon(Icons.Default.Settings, null, Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text("Вещи по умолчанию${if (defaultItems.isNotEmpty()) " (${defaultItems.size})" else ""}")
    }

    if (showDialog) {
        Dialog(onDismissRequest = { showDialog = false }) {
            Card {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(
                        "Вещи по умолчанию",
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Автоматически добавляются в каждый новый чеклист",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                    Spacer(Modifier.height(16.dp))
                    
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = newItemText,
                            onValueChange = { newItemText = it },
                            placeholder = { Text("Введите вещь...") },
                            modifier = Modifier.weight(1f),
                            singleLine = true
                        )
                        IconButton(
                            onClick = {
                                if (newItemText.trim().isNotEmpty()) {
                                    onAddItem(newItemText.trim())
                                    newItemText = ""
                                }
                            },
                            enabled = newItemText.trim().isNotEmpty()
                        ) {
                            Icon(Icons.Default.Add, "Добавить")
                        }
                    }
                    
                    Spacer(Modifier.height(12.dp))
                    
                    if (defaultItems.isEmpty()) {
                        Text(
                            "Список пуст",
                            Modifier.fillMaxWidth().padding(vertical = 32.dp),
                            textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                        )
                    } else {
                        LazyColumn(
                            Modifier.fillMaxWidth().heightIn(max = 300.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            items(defaultItems) { item ->
                                Surface(
                                    Modifier.fillMaxWidth(),
                                    color = MaterialTheme.colorScheme.surfaceVariant,
                                    shape = MaterialTheme.shapes.small
                                ) {
                                    Row(
                                        Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(item, Modifier.weight(1f))
                                        IconButton(
                                            onClick = { onRemoveItem(item) },
                                            modifier = Modifier.size(32.dp)
                                        ) {
                                            Icon(
                                                Icons.Default.Close,
                                                "Удалить",
                                                Modifier.size(16.dp),
                                                tint = MaterialTheme.colorScheme.error
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    Spacer(Modifier.height(16.dp))
                    Button(
                        onClick = { showDialog = false },
                        Modifier.fillMaxWidth()
                    ) {
                        Text("Закрыть")
                    }
                }
            }
        }
    }
}

