package com.luggify.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.luggify.app.data.datastore.UserPreferencesDataStore
import com.luggify.app.ui.screens.ChecklistScreen
import com.luggify.app.ui.screens.HomeScreen
import com.luggify.app.ui.screens.MyChecklistsScreen
import com.luggify.app.ui.theme.LuggifyTheme
import com.luggify.app.ui.viewmodel.LuggifyViewModel
import com.luggify.app.utils.UserIdHelper

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val userId = UserIdHelper.getUserId(this)
        val userPreferencesDataStore = UserPreferencesDataStore(this)
        val viewModel = LuggifyViewModel(
            context = this,
            userId = userId,
            userPreferencesDataStore = userPreferencesDataStore
        )
        
        setContent {
            LuggifyTheme {
                LuggifyApp(viewModel = viewModel)
            }
        }
    }
}

@Composable
fun LuggifyApp(viewModel: LuggifyViewModel) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = "home"
    ) {
        composable("home") {
            HomeScreen(
                viewModel = viewModel,
                onNavigateToChecklist = { slug ->
                    navController.navigate("checklist/$slug") {
                        popUpTo("home") { inclusive = false }
                    }
                },
                onNavigateToMyChecklists = {
                    navController.navigate("my-checklists") {
                        popUpTo("home") { inclusive = false }
                    }
                }
            )
        }
        
        composable("checklist/{slug}") { backStackEntry ->
            val slug = backStackEntry.arguments?.getString("slug") ?: return@composable
            ChecklistScreen(
                slug = slug,
                viewModel = viewModel,
                onNavigateBack = {
                    navController.popBackStack()
                    viewModel.navigateBack()
                }
            )
        }
        
        composable("my-checklists") {
            MyChecklistsScreen(
                viewModel = viewModel,
                onNavigateBack = {
                    navController.popBackStack()
                },
                onNavigateToChecklist = { slug ->
                    navController.navigate("checklist/$slug") {
                        popUpTo("my-checklists") { inclusive = false }
                    }
                }
            )
        }
    }
}

