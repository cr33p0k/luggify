export const pluralizeWord = (count, wordsRu, wordsEn, lang) => {
    if (lang === 'en') {
        return count === 1 ? wordsEn[0] : wordsEn[1];
    }

    // Russian declensions: 1 день, 2-4 дня, 5-0 дней.
    const cases = [2, 0, 1, 1, 1, 2];
    const idx = (count % 100 > 4 && count % 100 < 20)
        ? 2
        : cases[(count % 10 < 5) ? count % 10 : 5];

    return wordsRu[idx];
};

export const pluralize = (count, wordsRu, wordsEn, lang) => {
    return `${count} ${pluralizeWord(count, wordsRu, wordsEn, lang)}`;
};

export const formatDuration = (mins, lang) => {
    if (!mins) return null;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    if (lang === 'en') {
        return h > 0 ? `${h}h ${m > 0 ? m + 'm' : ''}` : `${m}m`;
    }
    return h > 0 ? `${h}ч ${m > 0 ? m + 'м' : ''}` : `${m}м`;
};

export const TRANSLATIONS = {
    ru: {
        heroTitle: "Куда собираемся?",
        heroSubtitle: "Введите город и даты — мы соберём идеальный чеклист для вашей поездки",
        addCity: "+ Добавить город",
        generate: " Поехали!",
        transport: "Транспорт:",
        gender: "Пол:",
        tripType: "Тип поездки:",
        pet: " С питомцем",
        allergies: " Аллергия",
        meds: " Лекарства",
        forecast: " Прогноз погоды",
        humidity: "Влажность",
        uv: "УФ-индекс",
        wind: "Ветер",
        kmh: "км/ч",
        errorChecklist: "Ошибка при загрузке чеклиста",
        errorServer: "Ошибка при запросе к серверу",
        fillAll: "Заполните все города и даты!",
        login: "Войти",
        logout: "Выйти",
        saveSuccess: " Чеклист сохранён в вашем аккаунте!",
        saveError: " Ошибка сохранения",
        restore: "Восстановить удалённые",
        reset: "Сбросить отметки",
        addItem: "+ Добавить вещь",
        cancel: "Отмена",
        newItem: "Новая вещь",
        exportCalendar: " В календарь",
        routeTitle: "Маршрут",

        // Options
        returnTransport: "Обратно:",
        plane: " Самолёт",
        train: " Поезд",
        car: " Авто",
        bus: " Автобус",
        unisex: " Любой",
        male: " Мужской",
        female: " Женский",
        vacation: " Отдых",
        business: " Работа",
        active: " Активный",
        beach: " Пляж",
        winter: " Зима",

        // Attractions
        whatToSee: "Что посмотреть",
        showMoreAttractions: "Показать больше",
        searchingAttractions: "Ищем интересные места…",
        openInGoogleMaps: "Открыть в Google Картах",

        // Flights
        flightsTitle: "Авиабилеты",
        searchingFlights: "Ищем авиабилеты…",
        outboundFlights: "Рейсы туда",
        inboundFlights: "Рейсы обратно",
        priceOnRequest: "Цена по запросу",
        directFlight: "Прямой",
        noCachedTickets: "К сожалению, кэшированных билетов на ваши точные даты мы не нашли.",
        searchReturnTickets: "Искать билеты туда и обратно",

        // Hotels
        hotelsTitle: "Жильё",
        adults: "Взрослые",
        children: "Дети",
        childAge: "Возраст ребенка",
        guests: "гостей",
        doneBtn: "Готово",
        searchingHotels: "Ищем отели…",
        showHotels: "Показать отели",
        goToBooking: "Перейти на Booking.com",
        searchDirectlyBooking: "Искать напрямую на Booking.com",
        noHotelsFound: "Отели не найдены для данного направления",
        ruWidgetsDisclaimer: "Для путешествий по России бронирование на Booking недоступно. Мы рекомендуем использовать проверенные российские сервисы:",
        perNight: "ночь",

        // eSIM
        esimTitle: "eSIM для интернета",
        esimDesc: "Виртуальная SIM-карта — подключитесь к интернету сразу по прилёту, без покупки местной SIM",
        esimDescBrowse: "eSIM доступны для 200+ стран — оставайтесь на связи в путешествии",
        chooseEsim: "Выбрать eSIM",
        browseEsim: "Посмотреть eSIM",

        // Profile page
        profileChecklists: " Чеклисты",
        profileAchievementsAndStats: " Достижения и статистика",
        myAchievements: "Мои достижения",
        yourPreferences: " Ваши предпочтения",
        frequentlyAdded: " Часто добавляете",
        frequentlyRemoved: " Часто удаляете",
        noChecklists: "У вас пока нет сохранённых чеклистов",
        createFirstChecklist: " Создать первый чеклист",
        shareString: "Поделиться",
        linkCopied: "Ссылка скопирована!",
        tripsStat: "Поездок",
        countriesStat: "Стран",
        citiesStat: "Городов",
        daysStat: "Дней",
        myChecklists: "чеклистов",
        myChecklists_1: "чеклист",
        myChecklists_2_4: "чеклиста",
        failedToLoadChecklists: "Не удалось загрузить чеклисты",
        deleteChecklistPrompt: "Удалить чеклист?",
        uploadAvatar: "Загрузить аватарку",
        statsPublic: "Открытый профиль",
        statsHidden: "Закрытый профиль",
        loadingStr: "Загрузка...",
        publicStatus: "Публичный",
        hiddenStatus: "Скрытый",
        deleteChecklistBtn: "Удалить чеклист",
        editProfile: "Редактировать профиль",
        bio: "О себе",
        socialLinks: "Социальные сети",
        saveProfile: "Сохранить",
        cancelEdit: "Отмена",

        // Subscriptions
        mySubs: "Мои подписки",
        myFollowers: "Мои подписчики",
        followersTab: "Подписчики",
        followingTab: "Подписки",
        followBtn: "Подписаться",
        unfollowBtn: "Отписаться",
        followBackBtn: "Подписаться в ответ",
        inviteBtn: "Пригласить",
        removeFollowerBtn: "Убрать",
        followsYou: "Подписан на вас",
        mutualFollow: "Вы подписаны друг на друга",
        youFollow: "Вы подписаны",
        inviteHint: "Приглашение в совместный чеклист открывается из самого чеклиста.",
        chooseChecklistTitle: "Куда пригласить",
        chooseChecklistDesc: "Выберите чеклист для приглашения.",
        noChecklistsToInvite: "У вас пока нет чеклистов для приглашения.",
        alreadyInChecklist: "Уже в чеклисте",
        inviteSent: "Приглашение отправлено",
        inviteAction: "Пригласить",
        subsEmptyState: "Здесь пока пусто.",
        followersStat: "Подписчики",
        followingStat: "Подписки",

        // Itinerary
        itineraryTitle: "План поездки",
        addEvent: "+ Добавить событие",
        eventTimePlaceholder: "Время (14:30)",
        eventTitlePlaceholder: "Название (Ужин, Музей...)",
        eventDescPlaceholder: "Описание или адрес (необязательно)",
        saveEventBtn: "Сохранить",
        noEvents: "План на этот день пока пуст",
        dayRoute: "День"
    },
    en: {
        heroTitle: "Where to?",
        heroSubtitle: "Enter city and dates — we'll generate the perfect packing list for your trip",
        addCity: "+ Add City",
        generate: " Let's go!",
        transport: "Transport:",
        gender: "Gender:",
        tripType: "Trip Type:",
        pet: " With Pet",
        allergies: " Allergies",
        meds: " Chronic Disease",
        forecast: " Weather Forecast",
        humidity: "Humidity",
        uv: "UV Index",
        wind: "Wind",
        kmh: "km/h",
        errorChecklist: "Error loading checklist",
        errorServer: "Server connection error",
        fillAll: "Please fill in all cities and dates!",
        login: "Login",
        logout: "Logout",
        saveSuccess: " Checklist saved to your account!",
        saveError: " Save error",
        restore: "Restore removed items",
        reset: "Reset checks",
        addItem: "+ Add Item",
        cancel: "Cancel",
        newItem: "New item",
        exportCalendar: " Add to Calendar",
        routeTitle: "Route",

        // Options
        returnTransport: "Return:",
        plane: " Plane",
        train: " Train",
        car: " Car",
        bus: " Bus",
        unisex: " Any",
        male: " Male",
        female: " Female",
        vacation: " Vacation",
        business: " Business",
        active: " Active",
        beach: " Beach",
        winter: " Winter",

        // Attractions
        whatToSee: "What to See",
        showMoreAttractions: "Show more",
        searchingAttractions: "Searching for interesting places…",
        openInGoogleMaps: "Open in Google Maps",

        // Flights
        flightsTitle: "Flights",
        searchingFlights: "Searching for flights…",
        outboundFlights: "Outbound flights",
        inboundFlights: "Inbound flights",
        priceOnRequest: "Price on request",
        directFlight: "Direct",
        noCachedTickets: "Unfortunately, we didn't find cached tickets for your exact dates.",
        searchReturnTickets: "Search round-trip tickets",

        // Hotels
        hotelsTitle: "Accommodation",
        adults: "Adults",
        children: "Children",
        childAge: "Child Age",
        guests: "guests",
        doneBtn: "Done",
        searchingHotels: "Searching for hotels…",
        showHotels: "Show hotels",
        goToBooking: "Go to Booking.com",
        searchDirectlyBooking: "Search directly on Booking.com",
        noHotelsFound: "No hotels found for this destination",
        ruWidgetsDisclaimer: "For traveling across Russia, Booking.com is unavailable. We recommend using verified local services:",
        perNight: "night",

        // eSIM
        esimTitle: "eSIM for Data",
        esimDesc: "Virtual SIM card — get connected right after landing, no need to buy a local SIM",
        esimDescBrowse: "eSIM available for 200+ countries — stay connected while traveling",
        chooseEsim: "Choose eSIM",
        browseEsim: "Browse eSIMs",

        // Profile page
        profileChecklists: " Checklists",
        profileAchievementsAndStats: " Achievements & Stats",
        myAchievements: "My Achievements",
        yourPreferences: " Your Preferences",
        editProfile: "Edit Profile",
        bio: "Bio",
        socialLinks: "Social Links",
        saveProfile: "Save",
        cancelEdit: "Cancel",
        frequentlyAdded: " Frequently added",
        frequentlyRemoved: " Frequently removed",
        noChecklists: "You don't have any saved checklists yet",
        createFirstChecklist: " Create your first checklist",
        shareString: "Share",
        linkCopied: "Link copied!",
        tripsStat: "Trips",
        countriesStat: "Countries",
        citiesStat: "Cities",
        daysStat: "Days",
        failedToLoadChecklists: "Failed to load checklists",
        deleteChecklistPrompt: "Delete checklist?",
        uploadAvatar: "Upload avatar",
        statsPublic: "Public profile",
        statsHidden: "Private profile",
        loadingStr: "Loading...",
        publicStatus: "Public",
        hiddenStatus: "Hidden",
        deleteChecklistBtn: "Delete checklist",

        // Subscriptions
        mySubs: "Following",
        myFollowers: "Followers",
        followersTab: "Followers",
        followingTab: "Following",
        followBtn: "Follow",
        unfollowBtn: "Unfollow",
        followBackBtn: "Follow Back",
        inviteBtn: "Invite",
        removeFollowerBtn: "Remove",
        followsYou: "Follows you",
        mutualFollow: "You follow each other",
        youFollow: "You follow this account",
        inviteHint: "Checklist invites are available from inside a checklist.",
        chooseChecklistTitle: "Invite To Checklist",
        chooseChecklistDesc: "Choose a checklist for the invite.",
        noChecklistsToInvite: "You have no checklists to invite into yet.",
        alreadyInChecklist: "Already in checklist",
        inviteSent: "Invite sent",
        inviteAction: "Invite",
        subsEmptyState: "It's empty here.",
        followersStat: "Followers",
        followingStat: "Following",

        // Itinerary
        itineraryTitle: "Day Plan",
        addEvent: "+ Add event",
        eventTimePlaceholder: "Time (14:30)",
        eventTitlePlaceholder: "Title (Dinner, Museum...)",
        eventDescPlaceholder: "Description or address (optional)",
        saveEventBtn: "Save",
        noEvents: "No plans for this day yet",
        dayRoute: "Day"
    }
};
