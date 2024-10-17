
import os, re, sys


class Categories:

    def __init__(self, rulefile):
        self.rulefile = rulefile
        self.existing_rules = self.read_rules()
        self.new_rules = []


    def read_rules(self):
        existing_rules = []
        if os.path.exists(self.rulefile):
            with open(self.rulefile, 'r', encoding='utf-8') as f:
                for line in f:
                    pattern, category = line.rstrip().split('\t')
                    existing_rules.append((pattern, category))
        else:
            with open(self.rulefile, 'a'):
                os.utime(self.rulefile, None)
        return existing_rules


    def get_category(self, description: str) -> str:
        for pattern, category in self.new_rules:
            if re.search(pattern, description):
                return category
        for pattern, category in self.existing_rules:
            if re.search(pattern, description):
                return category
        return None


    def write_rules(self):
        with open(self.rulefile, 'a', encoding='utf-8') as f:
            for pattern, category in self.new_rules:
                f.write(f'{pattern}\t{category}\n')
    

    def _should_i_go(self, ui):
        if ui == 'q':
            self.write_rules()
            sys.exit()
        return


    def _getcat(self,
            prompt = "Enter a new category, press Return to accept the current category, or 'q' to quit.",
            max_chars = 16):
        prompt = f"{prompt}\nCategories must be less than {max_chars} characters."
        cat = ''
        valid = False
        while not valid:
            cat = input(f"{prompt}\n=> ").lower()
            if len(cat) <= max_chars:
                valid = True
        return cat


    def categorize(self, description: str, suggested_cat: str = None, amount: int = None) -> None:
        description = description.lower()
        if cat := self.get_category(description):
            return cat
        else:
            amtstr = f'\n  Amount: {amount}' if amount else ''
            currcatstr = f'\n  Current category: {suggested_cat}' if suggested_cat else ''
            mypattern = input(f"Given:\n  Descr: [{description}]{amtstr}{currcatstr}\nWhat pattern? (or 'q' to quit)\n=> ").lower()
            self._should_i_go(mypattern)
            mycat = self._getcat()
            self._should_i_go(mycat)
            cat = mycat if mycat else suggested_cat
            self.new_rules.append((rf'{mypattern}', cat))
        return cat


def establish_new_rules(rulesfile_tsv, trainingfile_tsv):
    cats = Categories(rulesfile_tsv)
    with open(trainingfile_tsv, 'r', encoding='-utf-8') as f:
        header = next(f)
        for row in f:
            row = row.rstrip().lower()
            cat, desc = row.split('\t')
            _ = cats.categorize(desc, cat.lower())
        cats.write_rules()
        
