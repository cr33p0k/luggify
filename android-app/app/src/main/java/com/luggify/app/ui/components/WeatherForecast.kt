package com.luggify.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.luggify.app.data.models.DailyForecast
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun WeatherForecast(
    forecasts: List<DailyForecast>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "Прогноз погоды",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(bottom = 16.dp)
        )
        
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            items(forecasts) { forecast ->
                WeatherForecastCard(forecast = forecast)
            }
        }
    }
}

@Composable
fun WeatherForecastCard(
    forecast: DailyForecast,
    modifier: Modifier = Modifier
) {
    val dateFormat = SimpleDateFormat("dd.MM", Locale.getDefault())
    val date = try {
        val parsed = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).parse(forecast.date)
        parsed?.let { dateFormat.format(it) } ?: forecast.date
    } catch (e: Exception) {
        forecast.date
    }
    
    Card(
        modifier = modifier
            .width(120.dp)
            .height(180.dp), // Фиксированная высота для всех карточек
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.8f)
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = date,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            
            AsyncImage(
                model = "https://openweathermap.org/img/wn/${forecast.icon}@2x.png",
                contentDescription = forecast.condition,
                modifier = Modifier.size(60.dp)
            )
            
            Text(
                text = forecast.condition,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                modifier = Modifier.padding(horizontal = 4.dp),
                maxLines = 2,
                minLines = 2,
                textAlign = TextAlign.Center
            )
            
            Text(
                text = "${forecast.temp_min.toInt()}° / ${forecast.temp_max.toInt()}°C",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

