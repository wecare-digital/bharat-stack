function handler(event) {
  return {
    statusCode: 301,
    statusDescription: 'Moved Permanently',
    headers: {
      'location': { value: 'https://www.wecare.digital/selfcare' },
      'cache-control': { value: 'max-age=3600' }
    }
  };
}
