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

    // Диалог выбора даты начала
    if (showStartDatePicker) {
        val startDatePickerState = rememberDatePickerState(
            initialSelectedDateMillis = selectedStartDate.time
        )
        AlertDialog(
            onDismissRequest = { showStartDatePicker = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        startDatePickerState.selectedDateMillis?.let {
                            val date = Date(it)
                            selectedStartDate = date
                            startDateText = dateFormat.format(date)
                            onStartDateSelected(date)
                            showStartDatePicker = false
                            focusManager.clearFocus()
                        } ?: run {
                            showStartDatePicker = false
                        }
                    }
                ) {
                    Text("Выбрать")
                }
            },
            dismissButton = {
                TextButton(onClick = { showStartDatePicker = false }) {
                    Text("Отмена")
                }
            },
            title = { Text("Выберите дату отправления") },
            text = {
                DatePicker(state = startDatePickerState)
            }
        )
    }

    // Диалог выбора даты окончания
    if (showEndDatePicker) {
        val endDatePickerState = rememberDatePickerState(
            initialSelectedDateMillis = selectedEndDate.time
        )
        AlertDialog(
            onDismissRequest = { showEndDatePicker = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        endDatePickerState.selectedDateMillis?.let {
                            val date = Date(it)
                            selectedEndDate = date
                            endDateText = dateFormat.format(date)
                            onEndDateSelected(date)
                            showEndDatePicker = false
                            focusManager.clearFocus()
                        } ?: run {
                            showEndDatePicker = false
                        }
                    }
                ) {
                    Text("Выбрать")
                }
            },
            dismissButton = {
                TextButton(onClick = { showEndDatePicker = false }) {
                    Text("Отмена")
                }
            },
            title = { Text("Выберите дату возвращения") },
            text = {
                DatePicker(state = endDatePickerState)
            }
        )
    }
}

