const RAPID_API_KEY = 'dc4881aeb5mshe8df440e316ad7dp1564e3jsn8af63e1e4dd9';

export const geoApiOptions = {
  method: 'GET',
  headers: {
    'X-RapidAPI-Key': RAPID_API_KEY,
    'X-RapidAPI-Host': 'wft-geo-db.p.rapidapi.com',
  },
};

export const GEO_API_URL = 'https://wft-geo-db.p.rapidapi.com/v1/geo';
