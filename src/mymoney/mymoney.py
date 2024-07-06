#!/usr/bin/python3
"""
Takes transaction CSVs from accounts and tallies up ins and outs.
"""
import os, csv, locale, datetime, argparse, re, textwrap
import plotly.express as px
import pandas as pd
from shutil import rmtree
from markdown import markdown
from .categories import Categories
from .project import Project

locale.setlocale(locale.LC_ALL, 'en_US.UTF8')


def banner(msg: str = '') -> str:
  print(f'\n{"-"*80}\n{msg}\n{"-"*80}')


def total(amounts):
	'''A simple tally function'''
	ttl = 0
	for i in amounts:
		ttl += i
	return ttl


def valid_transaction(row, acct_cfg):
	if len(row) == 0 or len(row[acct_cfg['columns'][1]]) == 0:
		return False
	if 'rules' not in acct_cfg:
		return True
	for [testcol, pattern, action] in acct_cfg['rules']:
		if re.search(pattern, row[testcol]) is not None:
			if action == 'include':
				return True
			if action == 'exclude':
				return False
		else:
			if action == 'include':
				return False
			if action == 'exclude':
				return True


def slurp_account(prj: object, cats: object, account, date_col, desc_col, amt_col, date_format=None, order='descending'):
	'''Load and swizzle CSV data into our master transactions list'''
	filename = f'./input/{prj.period}/{account}.csv'
	acct_cfg = prj.config['format'][account]
	if not os.path.exists(filename):
		print(f'WARN: No CSV file found for the {account} account.')
		return
	else:
		banner(f'Slurping account: {account}')
	with open(filename, 'r', encoding='utf-8') as f:
		rows = csv.reader(f)
		for row in rows:
			if row[0][:1] == '#':
				continue
			row = [ x.lower() for x in row ]
			if 'date' in row[date_col]:
				continue
			if valid_transaction(row, acct_cfg):
				date = datetime.datetime.strptime(row[date_col], date_format).strftime('%Y-%m-%d') if date_format else row[date_col]
				cat = cats.categorize(description=row[desc_col], amount=row[amt_col])
				prj.transactions.append((
					date,                       # date
					locale.atof(row[amt_col]),  # amount
					account,                    # account
					row[desc_col],              # description
					cat			                # category
					))


def df_from_transactions(prj):

	# final statement balances
	# recording the balance at time of last transaction in CSV (or online for WFB).
	# Will use the final balance to determine the starting balance of the year.
	statement_ending_balance = total([ locale.atof(x.replace('$','')) for x in prj.config['current_balances'].values() ])

	# total transaction amounts starting from zero
	transactions_ending_balance_from_zero = total([ x[1] for x in prj.transactions ])

	# since transaction balance starts from zero, statement balance should be higher
	initial_transactions_balance = statement_ending_balance - transactions_ending_balance_from_zero

	# NOTE: I could verify to two ending balances match up by using the statement starting balances. hmm.

	# sort by date
	prj.transactions.sort(key=lambda x: x[0])	

	# to insert starting balance the day before the first transaction for better visualization
	startdate_minus_one = (datetime.datetime.strptime(prj.transactions[0][0], '%Y-%m-%d') - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

	# "prepend" that initial balance to the set
	prj.transactions = [(
		startdate_minus_one,             # date
		initial_transactions_balance,    # amount
		'all-together',                  # account
		'my initial balance',            # description
		None,                            # category
		)] + prj.transactions


	# tell pandas to not add ... when displaying the dataframe
	pd.set_option('display.max_rows', None)

	# From the transactions, create a DataFrame that we can easily reference
	df = pd.DataFrame(prj.transactions, columns=['Date', 'Amount', 'Account', 'Description', 'Category'])

	# add a running balance column for the graph
	df['Balance'] = df['Amount'].cumsum()

	# now that the balances are calculated, remove that initial entry from last year
	df = df.drop([0])

	return df


def slurp_accounts(prj, cats):
	'''populate prj.transactions with data from all accounts in the config file for this period'''
	for account, fmt in prj.config['format'].items():
		date_format = fmt['date_format'] if 'date_format' in fmt else None
		order = fmt['order'] if 'order' in fmt else 'descending'
		slurp_account(prj, cats, account, *fmt['columns'], date_format=date_format, order=order)


def balance_graph(prj, df):

	# now that the math's done, format floats to currency for display
	#df['Balance'] = df['Balance'].apply(lambda x: locale.currency(x, grouping=True))

	fig = px.line(df, x="Date", y="Balance", title='Balance, All accounts')
	fig.update_layout(yaxis_tickprefix = '$', yaxis_tickformat = ',.2f')
	fig.write_html(f"{prj.reports}/balance_{prj.period}.html", auto_open=False)


def dump_df(prj, df):
	df = df.set_index(['Date'])
	with open(f"{prj.reports}/transactions_{prj.period}.txt", 'w', encoding='utf-8') as f:
		with pd.option_context('display.max_rows', None, 'display.max_columns', None):
			f.write(df.to_string())


def monthly_net_income(prj, df):
	
	monthly_sums = df.groupby(pd.PeriodIndex(df['Date'], freq="M").strftime('%Y-%m'))['Amount'].sum()
	fig = px.bar(monthly_sums, x=monthly_sums.index, y="Amount",
			  title="Net monthly income (Profit+Loss)")
	fig.write_html(f"{prj.reports}/monthly_net_{prj.period}.html")


def categories_graph(prj, df):

	spending_df = df.loc[~df['Category'].isin(['income', 'transfer'])] # filter out income and transfers
	spending_df.loc[:,'Amount'] = spending_df['Amount'].mul(-1) # change - to + because it's an 'expenses' chart

	# add a Month column based on the dates
	months = spending_df.apply(lambda row: pd.to_datetime(row.Date).strftime('%Y-%m'), axis=1)
	spending_df = spending_df.assign(Month=months.values)

	fig = px.bar(spending_df, x="Month", y="Amount", color="Category", title=f"Expenses for {prj.period}")
	fig.write_html(f"{prj.reports}/spending_{prj.period}.html")

	avg = spending_df.groupby(pd.PeriodIndex(spending_df['Date'], freq="M"))['Amount'].sum().mean()
	return avg


def html_category_report_header(title):
	return textwrap.dedent(f'''\
		<!DOCTYPE html>
		<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<title>{title}</title>
			<style>
				body {{ font-family: sans-serif; margin: 2rem; }}
				h2 {{ margin: 2.2rem 0 0 0; font-size: 1rem; }}
				code {{ font-family: Consolas, monospace; }}
				.codeblock {{ background-color: #c0c0c0; border-radius: 6px; padding: 6px; }}
				pre {{ overflow-x: scroll; padding: 1rem; margin: 0; }}
			</style>
		</head>
		<body>
		  <h1>{title}</h1>
		''')


def categories_report(prj, df):

	s = f'Spending breakdown for {prj.period}'
	md_out = f'# {s}'
	html_out = html_category_report_header(s)
	sorted_df = df.sort_values(by=['Category', 'Date'])
	current_cat = ''
	cat_ttl = 0
	cat_header = ''
	cat_body = ''
	cat_html_body = ''
	for (date, amount, account, description, category, _) in sorted_df.values:
		if current_cat != category:
			if cat_body:
				md_out += f'\n\n\n## {cat_header} ${cat_ttl:10.2f}\n\n```{cat_body}```'
			if cat_html_body:
				html_cat_ttl = f'{cat_ttl:10.2f}'.replace(" ", "&nbsp;")
				html_out += f'\n\n\n<h2><code>{cat_header.replace(" ", "&nbsp;")}&nbsp;${html_cat_ttl}</code></h2>\n\n<div class="codeblock"><pre><code>{cat_html_body[1:-1]}\n</code></pre></div>'
			cat_header = f"{category.capitalize():<16}"
			cat_body = '\n'
			cat_html_body = '\n'
			cat_ttl = 0
			current_cat = category
		s = f"{date}    {amount:9.2f}    {account: <11} {description}\n"
		cat_body += f"        {s}"
		cat_html_body += f"   {s}"
		cat_ttl += amount

	with open(f"{prj.reports}/breakdown_{prj.period}.md", mode='w', encoding='utf-8') as of:
		of.write(md_out)
	with open(f"{prj.reports}/breakdown_{prj.period}.html", mode='w', encoding='utf-8') as of:
		of.write(html_out)


def year_to_date(prj):
	monthdirs = next(os.walk('input'))[1]
	year = prj.period[:4]
	ytddir = f'input/{year}YTD'
	rmtree(ytddir)
	os.makedirs(ytddir, exist_ok=True)
	mon_list = []
	asc_list = []
	desc_list = []
	# -- get list of available months
	for yrmon in sorted(monthdirs):
		if re.match(r'\d', yrmon[4:5]):
			mon_list.append(yrmon[4:])
	# -- separate banks with ascending rows from those with descending
	for key, bank in prj.config['format'].items():
		if 'order' in bank and bank['order'] == 'ascending':
			asc_list.append(key)
		else:
			desc_list.append(key)
	# -- aggregate the YTD rows (ascending ones first)
	for bank in asc_list:
		for mon in mon_list:
			wrag_file(f'input/{year}{mon}/{bank}.csv', f'{ytddir}/{bank}.csv')
	# -- and now the descending ones
	for bank in reversed(desc_list):
		for mon in reversed(mon_list):
			wrag_file(f'input/{year}{mon}/{bank}.csv', f'{ytddir}/{bank}.csv')


def wrag_file(infile, outfile):
	with open(outfile, 'a', encoding='utf-8') as ouf:
		with open(infile, 'r', encoding='utf-8') as inf:
			slurp = inf.read()
			ouf.write(slurp if slurp[-1:] == '\n' else f'{slurp}\n')


def main():

	parser = argparse.ArgumentParser()
	parser.add_argument('period', help="The time period you're interested in.")
	args = parser.parse_args()

	prj = Project(args.period)
	cats = Categories('cats-rule.tsv')

	if prj.period[4:7] == 'YTD':
		year_to_date(prj)

	# Sluuuuurp the transactions
	slurp_accounts(prj, cats)

	# record category-rules gathered during the slurps
	cats.write_rules()

	# get a sorted dataframe with balances from the transactions
	df = df_from_transactions(prj)

	#
	# Write reports
	#

	# HTML running balance line graph
	balance_graph(prj, df)

	# Text dump of all the transactions (the dataframe)
	dump_df(prj, df)

	# HTML graph of monthly net income (P+L)
	monthly_net_income(prj, df)

	# Markdown and HTML document of transactions grouped by category
	categories_report(prj, df)

	# HTML bar graph of categorized expenses by month
	avg = categories_graph(prj, df)

	# Ending balance and average monthly spending
	s = textwrap.dedent(f'''\
		
		---------------------------------------
		 Average monthly spending: {locale.currency(avg*-1, grouping=True)}
		 Statement ending balance: {locale.currency(df["Balance"].iloc[-1], grouping=True)}
		---------------------------------------
		''')
	banner(s)
	with open(f"{prj.reports}/avg_and_balance.txt", 'w', encoding='utf-8') as f:
		f.write(s)




if __name__=="__main__":
	main()

