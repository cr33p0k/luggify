package com.luggify.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateRangePicker(
    startDate: Date?,
    endDate: Date?,
    onStartDateSelected: (Date) -> Unit,
    onEndDateSelected: (Date) -> Unit,
    modifier: Modifier = Modifier
) {
    var showStartDatePicker by remember { mutableStateOf(false) }
    var showEndDatePicker by remember { mutableStateOf(false) }
    
    var selectedStartDate by remember(startDate) { mutableStateOf(startDate ?: Date()) }
    var selectedEndDate by remember(endDate) { mutableStateOf(endDate ?: Date()) }
    
    // Состояния для текстовых полей
    val dateFormat = remember { SimpleDateFormat("dd.MM.yyyy", Locale.getDefault()) }
    var startDateText by remember(startDate) { 
        mutableStateOf(startDate?.let { dateFormat.format(it) } ?: "") 
    }
    var endDateText by remember(endDate) { 
        mutableStateOf(endDate?.let { dateFormat.format(it) } ?: "") 
    }
    
    val focusManager = LocalFocusManager.current
    
    // Обновляем состояния при изменении дат извне
    LaunchedEffect(startDate) {
        startDate?.let {
            selectedStartDate = it
            startDateText = dateFormat.format(it)
        }
    }
    
    LaunchedEffect(endDate) {
        endDate?.let {
            selectedEndDate = it
            endDateText = dateFormat.format(it)
        }
    }
    
    // Функция парсинга даты из текста
    val parseDate: (String) -> Date? = { text ->
        try {
            dateFormat.parse(text)
        } catch (e: Exception) {
            null
        }
    }

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Дата начала
        OutlinedTextField(
            value = startDateText,
            onValueChange = { newText ->
                startDateText = newText
                parseDate(newText)?.let { date ->
                    selectedStartDate = date
                    onStartDateSelected(date)
                }
            },
            label = { Text("Отправление") },
            placeholder = { Text("dd.mm.yyyy") },
            modifier = Modifier.weight(1f),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline
            ),
            trailingIcon = {
                IconButton(
                    onClick = { showStartDatePicker = true }
                ) {
                    Icon(
                        imageVector = Icons.Default.DateRange,
                        contentDescription = "Выбрать дату"
                    )
                }
            },
            singleLine = true
        )

        // Дата окончания
        OutlinedTextField(
            value = endDateText,
            onValueChange = { newText ->
                endDateText = newText
                parseDate(newText)?.let { date ->
                    selectedEndDate = date
                    onEndDateSelected(date)
                }
            },
            label = { Text("Возвращение") },
            placeholder = { Text("dd.mm.yyyy") },
            modifier = Modifier.weight(1f),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline
            ),
            trailingIcon = {
                IconButton(
                    onClick = { showEndDatePicker = true }
                ) {
                    Icon(
                        imageVector = Icons.Default.DateRange,
                        contentDescription = "Выбрать дату"
                    )
                }
            },
            singleLine = true
        )
    }

    // Получаем текущую дату (сегодня) для ограничения минимальной даты
    val today = remember {
        val calendar = Calendar.getInstance()
        calendar.set(Calendar.HOUR_OF_DAY, 0)
        calendar.set(Calendar.MINUTE, 0)
        calendar.set(Calendar.SECOND, 0)
        calendar.set(Calendar.MILLISECOND, 0)
        calendar.timeInMillis
    }
    
    // Диалог выбора даты начала
    if (showStartDatePicker) {
        val startDatePickerState = rememberDatePickerState(
            initialSelectedDateMillis = selectedStartDate.time
        )
        Dialog(
            onDismissRequest = { showStartDatePicker = false },
            properties = DialogProperties(
                usePlatformDefaultWidth = false
            )
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth(0.95f)
                    .wrapContentHeight(),
                shape = MaterialTheme.shapes.extraLarge
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Выберите дату отправления",
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )
                    
                    DatePicker(
                        state = startDatePickerState,
                        modifier = Modifier.fillMaxWidth()
                    )
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(onClick = { showStartDatePicker = false }) {
                            Text("Отмена")
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        TextButton(
                            onClick = {
                                startDatePickerState.selectedDateMillis?.let {
                                    val date = Date(it)
                                    // Проверяем, что дата не раньше сегодняшней
                                    if (date.time >= today) {
                                        selectedStartDate = date
                                        startDateText = dateFormat.format(date)
                                        onStartDateSelected(date)
                                        showStartDatePicker = false
                                        focusManager.clearFocus()
                                    } else {
                                        // Можно показать сообщение об ошибке, но пока просто закрываем
                                        showStartDatePicker = false
                                    }
                                } ?: run {
                                    showStartDatePicker = false
                                }
                            }
                        ) {
                            Text("Выбрать")
                        }
                    }
                }
            }
        }
    }

    // Диалог выбора даты окончания
    if (showEndDatePicker) {
        // Минимальная дата для окончания - либо дата начала, либо сегодня (если дата начала не выбрана)
        val minEndDate = remember(selectedStartDate, today) {
            if (selectedStartDate.time >= today) {
                selectedStartDate.time
            } else {
                today
            }
        }
        
        val endDatePickerState = rememberDatePickerState(
            initialSelectedDateMillis = selectedEndDate.time
        )
        Dialog(
            onDismissRequest = { showEndDatePicker = false },
            properties = DialogProperties(
                usePlatformDefaultWidth = false
            )
        ) {
            Card(
                modifier = Modifier
                    .fillMaxWidth(0.95f)
                    .wrapContentHeight(),
                shape = MaterialTheme.shapes.extraLarge
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Выберите дату возвращения",
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )
                    
                    DatePicker(
                        state = endDatePickerState,
                        modifier = Modifier.fillMaxWidth()
                    )
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(onClick = { showEndDatePicker = false }) {
                            Text("Отмена")
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        TextButton(
                            onClick = {
                                endDatePickerState.selectedDateMillis?.let {
                                    val date = Date(it)
                                    // Проверяем, что дата не раньше минимальной (дата начала или сегодня)
                                    if (date.time >= minEndDate) {
                                        selectedEndDate = date
                                        endDateText = dateFormat.format(date)
                                        onEndDateSelected(date)
                                        showEndDatePicker = false
                                        focusManager.clearFocus()
                                    } else {
                                        // Можно показать сообщение об ошибке, но пока просто закрываем
                                        showEndDatePicker = false
                                    }
                                } ?: run {
                                    showEndDatePicker = false
                                }
                            }
                        ) {
                            Text("Выбрать")
                        }
                    }
                }
            }
        }
    }
}

