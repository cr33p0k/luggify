package com.luggify.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.luggify.app.R
import com.luggify.app.ui.components.CitySelect
import com.luggify.app.ui.components.DateRangePicker
import com.luggify.app.ui.components.DefaultItemsManager
import com.luggify.app.ui.viewmodel.LuggifyViewModel

@Composable
fun HomeScreen(
    viewModel: LuggifyViewModel,
    onNavigateToChecklist: (String) -> Unit,
    onNavigateToMyChecklists: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val scrollState = rememberScrollState()

    LaunchedEffect(uiState.checklist?.slug) {
        uiState.checklist?.slug?.let { slug ->
            onNavigateToChecklist(slug)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scrollState)
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(vertical = 24.dp)
        ) {
            Image(
                painter = painterResource(id = R.drawable.ic_luggify_logo),
                contentDescription = "Luggify Logo",
                modifier = Modifier.size(80.dp),
                colorFilter = ColorFilter.tint(MaterialTheme.colorScheme.primary)
            )
            Text(
                text = "Luggify",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.primary
            )
        }

        CitySelect(
            selectedCity = uiState.selectedCity,
            cities = uiState.cities,
            isLoading = uiState.isLoadingCities,
            onCitySelected = { viewModel.selectCity(it) },
            onCityCleared = { viewModel.clearCity() },
            onSearchQueryChanged = { viewModel.searchCities(it) },
            modifier = Modifier.fillMaxWidth()
        )

        DateRangePicker(
            startDate = uiState.startDate,
            endDate = uiState.endDate,
            onStartDateSelected = { viewModel.setStartDate(it) },
            onEndDateSelected = { viewModel.setEndDate(it) },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(8.dp))

        Button(
            onClick = { viewModel.generatePackingList() },
            enabled = !uiState.isLoading && 
                     uiState.selectedCity != null && 
                     uiState.startDate != null && 
                     uiState.endDate != null,
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary
            )
        ) {
            if (uiState.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
                Spacer(modifier = Modifier.width(8.dp))
            }
            Text("Сгенерировать список")
        }

        OutlinedButton(
            onClick = { onNavigateToMyChecklists() },
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = MaterialTheme.colorScheme.primary
            )
        ) {
            Text("Мои чеклисты")
        }

        // Кнопка управления вещами по умолчанию
        DefaultItemsManager(
            defaultItems = uiState.defaultItems,
            onAddItem = { viewModel.addDefaultItem(it) },
            onRemoveItem = { viewModel.removeDefaultItem(it) },
            modifier = Modifier.fillMaxWidth()
        )

        uiState.error?.let { error ->
            Spacer(modifier = Modifier.height(8.dp))
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Text(
                    text = error,
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

