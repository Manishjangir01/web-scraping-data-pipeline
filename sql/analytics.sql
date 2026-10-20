-- SQL analytics for the books database. Every query starts with a name comment.

-- name: price_by_rating
SELECT rating,
       COUNT(*)              AS books,
       ROUND(AVG(price), 2)  AS avg_price,
       MIN(price)            AS min_price,
       MAX(price)            AS max_price
FROM books
GROUP BY rating
ORDER BY rating DESC;

-- name: stock_summary
SELECT CASE in_stock WHEN 1 THEN 'in stock' ELSE 'out of stock' END AS availability,
       COUNT(*)                                                      AS books,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM books), 1)     AS share_pct
FROM books
GROUP BY in_stock
ORDER BY in_stock DESC;

-- name: price_bands
SELECT CASE
         WHEN price < 20 THEN 'under 20'
         WHEN price < 40 THEN '20 to 39.99'
         WHEN price < 60 THEN '40 to 59.99'
         ELSE '60 and over'
       END AS price_band,
       COUNT(*) AS books
FROM books
GROUP BY price_band
ORDER BY MIN(price);

-- name: cheapest_five_star_in_stock
SELECT title, price
FROM books
WHERE rating = 5 AND in_stock = 1
ORDER BY price, title
LIMIT 10;

-- name: price_changes
SELECT b.title,
       MIN(h.price) AS lowest,
       MAX(h.price) AS highest,
       COUNT(*)     AS observations
FROM price_history h
JOIN books b ON b.url = h.url
GROUP BY h.url
HAVING COUNT(*) > 1
ORDER BY MAX(h.price) - MIN(h.price) DESC
LIMIT 10;

-- name: latest_runs
SELECT run_id, status, pages_fetched, raw_records, clean_records, rejected_records, new_books, price_changes
FROM scrape_runs
ORDER BY run_id DESC
LIMIT 5;
